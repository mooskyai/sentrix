"""Inspect one real Node SDK OTLP trace from stdin without saving or ingesting it.

This checks the *exact bytes* captured in memory by the diagnostic relay against
Sentrix's production protobuf decoder and ClickHouse row normalizer. It does not
prove the Sentrix HTTP receiver inserted those bytes into ClickHouse.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any
from uuid import UUID

from apps.telemetry.clickhouse_writer import normalize_otlp_batch
from apps.telemetry.protocol import OtlpDecodeError, OtlpSignal, decode_otlp_request
from apps.telemetry.sink import OtlpBatch

MAX_WIRE_BYTES = 2 * 1024 * 1024
SERVICE = "m7-node-express-runtime"
ENVIRONMENT = "integration"
RUN_MARKER = "sentrix.acceptance.run"


class WireMismatch(ValueError):
    """The submitted real OTLP trace does not match the expected SDK span."""


def _attributes(items: Any) -> dict[str, str]:
    return {item.key: item.value.string_value for item in items}


def inspect_wire(payload: bytes, *, run_id: str, trace_id: str) -> None:
    """Fail closed unless canonical decoder/normalizer produce one exact span."""
    if not payload or len(payload) > MAX_WIRE_BYTES:
        raise WireMismatch("Invalid OTLP payload size.")
    if not re.fullmatch(r"[a-f0-9]{32}", run_id) or not re.fullmatch(r"[a-f0-9]{32}", trace_id):
        raise WireMismatch("Invalid run or trace identifier.")
    try:
        message = decode_otlp_request(signal=OtlpSignal.TRACES, payload=payload)
    except OtlpDecodeError as exc:
        raise WireMismatch("Production decoder rejected the OTLP payload.") from exc
    entries = [
        (resource_spans.resource, span)
        for resource_spans in message.resource_spans
        for scope_spans in resource_spans.scope_spans
        for span in scope_spans.spans
    ]
    if len(entries) != 1:
        raise WireMismatch(f"Production decoder found {len(entries)} spans, expected 1.")
    resource, span = entries[0]
    labels = _attributes(resource.attributes)
    span_labels = _attributes(span.attributes)
    if (
        span.trace_id.hex() != trace_id
        or not span.span_id
        or span.name != "m7.node.checkout"
        or span.kind != 2
        or int(span.start_time_unix_nano) <= 0
        or int(span.end_time_unix_nano) <= int(span.start_time_unix_nano)
        or labels.get("service.name") != SERVICE
        or labels.get("deployment.environment.name") != ENVIRONMENT
        or labels.get(RUN_MARKER) != run_id
        or span_labels.get(RUN_MARKER) != run_id
        or span_labels.get("http.request.method") != "GET"
        or span_labels.get("http.route") != "/checkout"
    ):
        raise WireMismatch("SDK span identity, timestamps or attributes do not match.")
    # No ClickHouse writes: use fake UUIDs only to exercise production normalization.
    batch = OtlpBatch(
        organization_id=UUID(int=0),
        project_id=UUID(int=0),
        api_key_id=UUID(int=0),
        signal=OtlpSignal.TRACES,
        message=message,
    )
    table, columns, rows = normalize_otlp_batch(batch)
    if table != "sentrix_spans" or len(rows) != 1:
        raise WireMismatch("Production normalization did not yield exactly one span row.")
    normalized = dict(zip(columns, rows[0], strict=True))
    if (
        normalized["trace_id"] != trace_id
        or normalized["service_name"] != SERVICE
        or normalized["environment"] != ENVIRONMENT
        or normalized["span_name"] != "m7.node.checkout"
        or normalized["resource_attributes"].get(RUN_MARKER) != run_id
    ):
        raise WireMismatch("Normalized span did not retain the SDK evidence.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect ephemeral Node OTLP bytes in API container"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    args = parser.parse_args()
    if sys.stdin.isatty():
        print("Send OTLP bytes on stdin; no file paths or secrets.", file=sys.stderr)
        return 2
    try:
        payload = sys.stdin.buffer.read(MAX_WIRE_BYTES + 1)
        inspect_wire(payload, run_id=args.run_id, trace_id=args.trace_id)
    except WireMismatch as exc:
        print(f"Django wire inspection NOT VERIFIED: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Django wire inspection unavailable.", file=sys.stderr)
        return 1
    print("Django wire inspection VERIFIED: 1 decoded SDK span, 1 normalized ClickHouse row.")
    print("This is not proof that the HTTP receiver persisted the span.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
