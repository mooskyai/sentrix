"""Separate-process OTLP/HTTP smoke producer for Sentrix M6 operator acceptance.

This tool sends real protobuf over HTTP; it does not certify persistence, tenancy,
manual browser behavior, or a framework integration. No project key is logged.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from google.protobuf.message import Message  # type: ignore[import-untyped]
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, InstrumentationScope, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs, SeverityNumber
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Gauge,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

SERVICE_NAMES = ("m6-acceptance-gateway", "m6-acceptance-checkout", "m6-acceptance-payments")
ENVIRONMENT = "acceptance"
SCOPE = "sentrix.m6.acceptance.smoke"
METRIC_NAME = "sentrix.m6.acceptance.requests"


@dataclass(frozen=True)
class RunEvidence:
    run_id: str
    trace_id: bytes
    span_ids: tuple[bytes, bytes, bytes]
    timestamp_ns: int

    @classmethod
    def create(cls) -> RunEvidence:
        return cls(
            run_id=uuid4().hex,
            trace_id=uuid4().bytes,
            span_ids=(uuid4().bytes[:8], uuid4().bytes[:8], uuid4().bytes[:8]),
            timestamp_ns=time.time_ns(),
        )

    @property
    def host_name(self) -> str:
        return f"sentrix-acceptance-{self.run_id[:12]}"


def _attribute(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def _resource(evidence: RunEvidence, service_name: str) -> Resource:
    return Resource(
        attributes=[
            _attribute("service.name", service_name),
            _attribute("deployment.environment.name", ENVIRONMENT),
            _attribute("host.name", evidence.host_name),
            _attribute("k8s.cluster.name", "sentrix-acceptance-cluster"),
            _attribute("k8s.namespace.name", "sentrix-acceptance"),
            _attribute("k8s.pod.name", f"{service_name}-{evidence.run_id[:8]}"),
            _attribute("k8s.container.name", "app"),
            _attribute("sentrix.acceptance.run", evidence.run_id),
        ]
    )


def build_payloads(evidence: RunEvidence) -> dict[str, Message]:
    """Construct three correlated spans plus one metric and log per service."""
    traces = ExportTraceServiceRequest()
    metrics = ExportMetricsServiceRequest()
    logs = ExportLogsServiceRequest()

    for index, service_name in enumerate(SERVICE_NAMES):
        resource = _resource(evidence, service_name)
        span = Span(
            trace_id=evidence.trace_id,
            span_id=evidence.span_ids[index],
            parent_span_id=evidence.span_ids[index - 1] if index else b"",
            name=f"m6.acceptance.{service_name}",
            kind=Span.SPAN_KIND_SERVER,
            start_time_unix_nano=evidence.timestamp_ns + (index * 1_000_000),
            end_time_unix_nano=evidence.timestamp_ns + 30_000_000,
            attributes=[_attribute("sentrix.acceptance.run", evidence.run_id)],
        )
        traces.resource_spans.append(
            ResourceSpans(
                resource=resource,
                scope_spans=[ScopeSpans(scope=InstrumentationScope(name=SCOPE), spans=[span])],
            )
        )
        metrics.resource_metrics.append(
            ResourceMetrics(
                resource=resource,
                scope_metrics=[
                    ScopeMetrics(
                        scope=InstrumentationScope(name=SCOPE),
                        metrics=[
                            Metric(
                                name=METRIC_NAME,
                                gauge=Gauge(
                                    data_points=[
                                        NumberDataPoint(
                                            time_unix_nano=evidence.timestamp_ns,
                                            as_int=1,
                                        )
                                    ]
                                ),
                            )
                        ],
                    )
                ],
            )
        )
        logs.resource_logs.append(
            ResourceLogs(
                resource=resource,
                scope_logs=[
                    ScopeLogs(
                        scope=InstrumentationScope(name=SCOPE),
                        log_records=[
                            LogRecord(
                                time_unix_nano=evidence.timestamp_ns,
                                severity_number=SeverityNumber.SEVERITY_NUMBER_INFO,
                                severity_text="INFO",
                                body=AnyValue(string_value=f"M6 acceptance {service_name}"),
                                trace_id=evidence.trace_id,
                                span_id=evidence.span_ids[index],
                            )
                        ],
                    )
                ],
            )
        )
    return {"traces": traces, "metrics": metrics, "logs": logs}


def validate_base_url(value: str) -> str:
    """Never send bearer credentials over non-local HTTP or in URL components."""
    url = urlsplit(value)
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Base URL must be an HTTP(S) origin without credentials, path, or query.")
    if url.scheme == "http" and url.hostname not in (
        "localhost",
        "127.0.0.1",
        "::1",
        "api",
        "host.docker.internal",
    ):
        raise ValueError("Non-local endpoints must use HTTPS.")
    return value.rstrip("/")


def send_payloads(base_url: str, token: str, payloads: dict[str, Message]) -> None:
    for signal, payload in payloads.items():
        request = Request(
            f"{base_url}/v1/{signal}",
            data=payload.SerializeToString(),
            headers={
                "Content-Type": "application/x-protobuf",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError(f"OTLP {signal} returned HTTP {response.status}.")
        except HTTPError as exc:
            raise RuntimeError(f"OTLP {signal} rejected (HTTP {exc.code}).") from None
        except URLError:
            raise RuntimeError(
                f"OTLP {signal} connection failed; check endpoint and API health."
            ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send nonsecret M6 acceptance OTLP evidence")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        origin = validate_base_url(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.stdin.isatty():
        print(
            "Supply a temporary project key on stdin (do not pass it as a CLI argument).",
            file=sys.stderr,
        )
        return 2
    token = sys.stdin.readline().strip()
    if not token:
        print("Missing project key on stdin.", file=sys.stderr)
        return 2
    evidence = RunEvidence.create()
    try:
        send_payloads(origin, token, build_payloads(evidence))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        token = ""
    observed_at = datetime.fromtimestamp(evidence.timestamp_ns / 1e9, tz=UTC)
    print("OTLP/HTTP accepted three signals (HTTP 200 each). Verify persistence in Sentrix UI.")
    print(f"Run ID: {evidence.run_id}")
    print(f"Trace ID: {evidence.trace_id.hex()}")
    print(f"Time (UTC): {observed_at.isoformat()}")
    print(f"Services: {', '.join(SERVICE_NAMES)} (environment: {ENVIRONMENT})")
    print(f"Observed host: {evidence.host_name}; cluster: sentrix-acceptance-cluster")
    print("Expected graph: gateway -> checkout -> payments (two directed edges).")
    print("The output is NOT proof of read-back, foreign-user isolation or browser acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
