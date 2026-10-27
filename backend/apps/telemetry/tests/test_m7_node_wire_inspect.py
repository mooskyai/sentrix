from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from scripts.m7_node_wire_inspect import WireMismatch, inspect_wire


def _attr(target: object, key: str, value: str) -> None:
    item = target.attributes.add()  # type: ignore[attr-defined]
    item.key = key
    item.value.string_value = value


def _wire(*, run: str, trace: str, empty: bool = False) -> bytes:
    message = ExportTraceServiceRequest()
    group = message.resource_spans.add()
    _attr(group.resource, "service.name", "m7-node-express-runtime")
    _attr(group.resource, "deployment.environment.name", "integration")
    _attr(group.resource, "sentrix.acceptance.run", run)
    if not empty:
        span = group.scope_spans.add().spans.add()
        span.trace_id = bytes.fromhex(trace)
        span.span_id = b"\x01" * 8
        span.name = "m7.node.checkout"
        span.kind = 2
        span.start_time_unix_nano = 1_780_000_000_000_000_000
        span.end_time_unix_nano = 1_780_000_000_030_000_000
        _attr(span, "sentrix.acceptance.run", run)
        _attr(span, "http.request.method", "GET")
        _attr(span, "http.route", "/checkout")
    return cast(bytes, message.SerializeToString())


def test_realistic_node_wire_yields_one_canonical_normalized_row() -> None:
    run, trace = uuid4().hex, uuid4().hex
    inspect_wire(_wire(run=run, trace=trace), run_id=run, trace_id=trace)


def test_empty_nested_resource_group_is_not_acknowledged_as_persisted() -> None:
    run, trace = uuid4().hex, uuid4().hex
    with pytest.raises(WireMismatch, match="found 0 spans"):
        inspect_wire(_wire(run=run, trace=trace, empty=True), run_id=run, trace_id=trace)


def test_wrong_trace_id_is_not_accepted() -> None:
    run, trace = uuid4().hex, uuid4().hex
    with pytest.raises(WireMismatch, match="do not match"):
        inspect_wire(_wire(run=run, trace=trace), run_id=run, trace_id=uuid4().hex)


def test_corrupt_wire_is_rejected_without_raw_body_logging() -> None:
    with pytest.raises(WireMismatch, match="decoder rejected"):
        inspect_wire(b"\x80", run_id=uuid4().hex, trace_id=uuid4().hex)
