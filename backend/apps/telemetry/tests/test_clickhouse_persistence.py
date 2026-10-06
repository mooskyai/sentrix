from __future__ import annotations

import time
from typing import Any, cast
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, InstrumentationScope, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import (
    LogRecord,
    ResourceLogs,
    ScopeLogs,
    SeverityNumber,
)
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    ExponentialHistogram,
    ExponentialHistogramDataPoint,
    Gauge,
    Histogram,
    HistogramDataPoint,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
    Summary,
    SummaryDataPoint,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
from opentelemetry.sdk.resources import Resource as SdkResource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import sink as telemetry_sink
from apps.telemetry.clickhouse_schema import ensure_clickhouse_schema, get_clickhouse_client
from apps.telemetry.clickhouse_writer import normalize_otlp_batch
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE, OtlpSignal
from apps.telemetry.sink import OtlpBatch, TelemetrySinkUnavailable


def _key_value(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def _resource(run_id: str, service_name: str) -> Resource:
    return Resource(
        attributes=[
            _key_value("service.name", service_name),
            _key_value("deployment.environment.name", "integration"),
            _key_value("sentrix.test.run", run_id),
        ]
    )


def _scope() -> InstrumentationScope:
    return InstrumentationScope(name="sentrix.persistence.test", version="1.0.0")


def _metric_request(run_id: str) -> ExportMetricsServiceRequest:
    now = time.time_ns()
    return ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                resource=_resource(run_id, "sentrix-metric-e2e"),
                scope_metrics=[
                    ScopeMetrics(
                        scope=_scope(),
                        metrics=[
                            Metric(
                                name=f"sentrix.e2e.{run_id}",
                                gauge=Gauge(
                                    data_points=[
                                        NumberDataPoint(
                                            time_unix_nano=now,
                                            as_int=7,
                                            attributes=[_key_value("route", "/checkout")],
                                        )
                                    ]
                                ),
                            )
                        ],
                    )
                ],
            )
        ]
    )


def _log_request(run_id: str, body: str) -> ExportLogsServiceRequest:
    now = time.time_ns()
    return ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                resource=_resource(run_id, "sentrix-log-e2e"),
                scope_logs=[
                    ScopeLogs(
                        scope=_scope(),
                        log_records=[
                            LogRecord(
                                time_unix_nano=now,
                                severity_number=SeverityNumber.SEVERITY_NUMBER_INFO,
                                severity_text="INFO",
                                body=AnyValue(string_value=body),
                                trace_id=b"\x11" * 16,
                                span_id=b"\x22" * 8,
                                attributes=[_key_value("component", "checkout")],
                            )
                        ],
                    )
                ],
            )
        ]
    )


def _trace_request(run_id: str, span_name: str) -> ExportTraceServiceRequest:
    start = time.time_ns()
    return ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=_resource(run_id, "sentrix-trace-e2e"),
                scope_spans=[
                    ScopeSpans(
                        scope=_scope(),
                        spans=[
                            Span(
                                trace_id=b"\x33" * 16,
                                span_id=b"\x44" * 8,
                                parent_span_id=b"\x55" * 8,
                                name=span_name,
                                start_time_unix_nano=start,
                                end_time_unix_nano=start + 5_000_000,
                                attributes=[_key_value("operation", "checkout")],
                            )
                        ],
                    )
                ],
            )
        ]
    )


def _credential(prefix: str) -> tuple[str, Project]:
    unique = uuid4().hex[:12]
    user = User.objects.create_user(username=f"{prefix}-{unique}")
    organization = Organization.objects.create(
        name=f"{prefix} organization",
        slug=f"{prefix}-{unique}",
    )
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.OWNER,
    )
    project = Project.objects.create(
        organization=organization,
        name=f"{prefix} project",
        slug=f"{prefix}-{unique}",
        created_by=user,
    )
    _api_key, token = create_project_api_key(
        project=project,
        name=f"{prefix} exporter",
        created_by=user,
    )
    return token, project


def _post_otlp(path: str, token: str, message: Any) -> Any:
    return APIClient().post(
        path,
        data=message.SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _query(sql: str) -> list[tuple[Any, ...]]:
    client = get_clickhouse_client()
    try:
        return cast(list[tuple[Any, ...]], client.query(sql).result_rows)
    finally:
        client.close()


@pytest.fixture(scope="module")
def live_clickhouse_schema() -> None:
    client = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(client)
    finally:
        client.close()


def test_metric_family_normalization_preserves_shapes() -> None:
    now = time.time_ns()
    resource = _resource(uuid4().hex, "metric-shapes")
    scope = _scope()
    message = ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                resource=resource,
                scope_metrics=[
                    ScopeMetrics(
                        scope=scope,
                        metrics=[
                            Metric(
                                name="gauge",
                                gauge=Gauge(
                                    data_points=[NumberDataPoint(time_unix_nano=now, as_int=4)]
                                ),
                            ),
                            Metric(
                                name="histogram",
                                histogram=Histogram(
                                    data_points=[
                                        HistogramDataPoint(
                                            time_unix_nano=now,
                                            count=2,
                                            sum=3.0,
                                            bucket_counts=[1, 1],
                                            explicit_bounds=[1.0],
                                        )
                                    ]
                                ),
                            ),
                            Metric(
                                name="exponential",
                                exponential_histogram=ExponentialHistogram(
                                    data_points=[
                                        ExponentialHistogramDataPoint(
                                            time_unix_nano=now,
                                            count=1,
                                            sum=2.0,
                                            scale=0,
                                            zero_count=0,
                                            positive=ExponentialHistogramDataPoint.Buckets(
                                                offset=0,
                                                bucket_counts=[1],
                                            ),
                                        )
                                    ]
                                ),
                            ),
                            Metric(
                                name="summary",
                                summary=Summary(
                                    data_points=[
                                        SummaryDataPoint(
                                            time_unix_nano=now,
                                            count=1,
                                            sum=2.0,
                                            quantile_values=[
                                                SummaryDataPoint.ValueAtQuantile(
                                                    quantile=0.5,
                                                    value=2.0,
                                                )
                                            ],
                                        )
                                    ]
                                ),
                            ),
                        ],
                    )
                ],
            )
        ]
    )
    batch = OtlpBatch(
        organization_id=uuid4(),
        project_id=uuid4(),
        api_key_id=uuid4(),
        signal=OtlpSignal.METRICS,
        message=message,
    )

    table, columns, rows = normalize_otlp_batch(batch)
    metric_type_index = columns.index("metric_type")
    value_type_index = columns.index("value_type")

    assert table == "sentrix_metrics"
    assert [row[metric_type_index] for row in rows] == [
        "gauge",
        "histogram",
        "exponential_histogram",
        "summary",
    ]
    assert [row[value_type_index] for row in rows] == [
        "int",
        "histogram",
        "exponential_histogram",
        "summary",
    ]


def test_clickhouse_insert_failure_becomes_retryable_sink_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingClient:
        closed = False

        def insert(
            self,
            table_name: str,
            rows: list[list[Any]],
            *,
            column_names: list[str],
        ) -> None:
            del table_name, rows, column_names
            raise RuntimeError("clickhouse unavailable")

        def close(self) -> None:
            self.closed = True

    client = FailingClient()
    monkeypatch.setattr(telemetry_sink, "get_clickhouse_client", lambda: client)
    batch = OtlpBatch(
        organization_id=uuid4(),
        project_id=uuid4(),
        api_key_id=uuid4(),
        signal=OtlpSignal.METRICS,
        message=_metric_request(uuid4().hex),
    )

    with pytest.raises(TelemetrySinkUnavailable):
        telemetry_sink.submit_otlp_batch(batch)

    assert client.closed


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_all_otlp_signals_persist_to_clickhouse(live_clickhouse_schema: None) -> None:
    del live_clickhouse_schema
    token, project = _credential("signals")
    run_id = uuid4().hex
    metric_name = f"sentrix.e2e.{run_id}"
    log_body = f"sentrix-log-{run_id}"
    span_name = f"sentrix-span-{run_id}"

    assert _post_otlp("/v1/metrics", token, _metric_request(run_id)).status_code == 200
    assert _post_otlp("/v1/logs", token, _log_request(run_id, log_body)).status_code == 200
    assert _post_otlp("/v1/traces", token, _trace_request(run_id, span_name)).status_code == 200

    metric_rows = _query(
        "SELECT service_name, environment, number_value "
        "FROM sentrix_metrics "
        f"WHERE project_id = toUUID('{project.id}') AND metric_name = '{metric_name}'"
    )
    log_rows = _query(
        "SELECT service_name, body, trace_id, span_id "
        "FROM sentrix_logs "
        f"WHERE project_id = toUUID('{project.id}') AND body = '{log_body}'"
    )
    span_rows = _query(
        "SELECT service_name, span_name, parent_span_id, duration_ns "
        "FROM sentrix_spans "
        f"WHERE project_id = toUUID('{project.id}') AND span_name = '{span_name}'"
    )

    assert metric_rows == [("sentrix-metric-e2e", "integration", 7.0)]
    assert log_rows == [("sentrix-log-e2e", log_body, b"11" * 16, b"22" * 8)]
    assert span_rows == [("sentrix-trace-e2e", span_name, b"55" * 8, 5_000_000)]


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_project_credentials_keep_clickhouse_rows_isolated(live_clickhouse_schema: None) -> None:
    del live_clickhouse_schema
    token_a, project_a = _credential("tenant-a")
    token_b, project_b = _credential("tenant-b")
    run_id = uuid4().hex
    body_a = f"tenant-a-{run_id}"
    body_b = f"tenant-b-{run_id}"

    assert _post_otlp("/v1/logs", token_a, _log_request(run_id, body_a)).status_code == 200
    assert _post_otlp("/v1/logs", token_b, _log_request(run_id, body_b)).status_code == 200

    rows_a = _query(
        "SELECT body FROM sentrix_logs "
        f"WHERE project_id = toUUID('{project_a.id}') AND body IN ('{body_a}', '{body_b}')"
    )
    rows_b = _query(
        "SELECT body FROM sentrix_logs "
        f"WHERE project_id = toUUID('{project_b.id}') AND body IN ('{body_a}', '{body_b}')"
    )

    assert rows_a == [(body_a,)]
    assert rows_b == [(body_b,)]


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_real_opentelemetry_http_exporter_persists_span(
    live_server: Any, live_clickhouse_schema: None
) -> None:
    del live_clickhouse_schema
    token, project = _credential("sdk")
    run_id = uuid4().hex
    span_name = f"sdk-span-{run_id}"
    provider = TracerProvider(
        resource=SdkResource.create(
            {
                "service.name": "sentrix-sdk-e2e",
                "deployment.environment.name": "integration",
                "sentrix.test.run": run_id,
            }
        )
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{live_server.url}/v1/traces",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("sentrix.sdk.e2e", "1.0.0")

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("sentrix.integration", True)

    provider.shutdown()

    rows = _query(
        "SELECT service_name, scope_name, span_name "
        "FROM sentrix_spans "
        f"WHERE project_id = toUUID('{project.id}') AND span_name = '{span_name}'"
    )
    assert rows == [("sentrix-sdk-e2e", "sentrix.sdk.e2e", span_name)]
