"""M7.3.2 Node SDK persistence verification, without fabricated DB acceptance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from scripts import m7_node_readback as readback
from scripts.m6_readback import parse_run_window


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.sql = ""
        self.parameters: dict[str, Any] = {}

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeResult:
        self.sql = sql
        self.parameters = parameters
        return FakeResult(self.rows)


def _window() -> Any:
    return parse_run_window("a" * 32, "b" * 32, "2026-10-25T07:00:00Z")


def _row() -> tuple[Any, ...]:
    return (
        "b" * 32,
        "c" * 16,
        readback.SPAN_NAME,
        2,
        {
            readback.RUN_ATTRIBUTE: "a" * 32,
            "service.name": readback.SERVICE,
            "deployment.environment.name": readback.ENVIRONMENT,
        },
        {
            readback.RUN_ATTRIBUTE: "a" * 32,
            "http.request.method": "GET",
            "http.route": "/checkout",
        },
        datetime(2026, 10, 25, 7, 0, tzinfo=UTC),
        datetime(2026, 10, 25, 7, 0, 0, 1000, tzinfo=UTC),
    )


def test_typed_tenant_bounded_run_readback() -> None:
    org_id, project_id = UUID(int=1), UUID(int=2)
    client = FakeClient([_row()])
    rows = readback.read_trace_rows(
        client, _window(), organization_id=org_id, project_id=project_id
    )
    readback.verify_trace(_window(), rows)
    assert client.parameters["organization_id"] == org_id
    assert client.parameters["project_id"] == project_id
    assert client.parameters["service"] == readback.SERVICE
    assert client.parameters["environment"] == readback.ENVIRONMENT
    assert client.parameters["run_id"] == "a" * 32
    assert "organization_id = {organization_id:UUID}" in client.sql
    assert "project_id = {project_id:UUID}" in client.sql
    assert "resource_attributes['sentrix.acceptance.run'] = {run_id:String}" in client.sql
    assert "LIMIT 2" in client.sql
    assert "max_execution_time = 8" in client.sql
    assert "max_rows_to_read = 250000" in client.sql


@pytest.mark.parametrize("rows", [[], [_row(), _row()]])
def test_rejects_missing_and_duplicate_evidence(rows: list[tuple[Any, ...]]) -> None:
    with pytest.raises(readback.NodeTraceNotVerified):
        readback.verify_trace(_window(), rows)


@pytest.mark.parametrize(
    "index,replacement",
    [
        (0, "f" * 32),
        (1, "0" * 16),
        (2, "unknown.operation"),
        (3, 1),
        (3, "2"),
        (4, {readback.RUN_ATTRIBUTE: "wrong"}),
        (5, {readback.RUN_ATTRIBUTE: "wrong"}),
        (6, "not datetime"),
        (7, None),
    ],
)
def test_rejects_malformed_evidence(index: int, replacement: Any) -> None:
    row = list(_row())
    row[index] = replacement
    with pytest.raises(readback.NodeTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


@pytest.mark.parametrize(
    "field,value",
    [
        ("sentrix.acceptance.run", "bad"),
        ("http.request.method", "POST"),
        ("http.route", "/wrong"),
    ],
)
def test_rejects_wrong_request_attributes(field: str, value: str) -> None:
    row = list(_row())
    attrs = dict(row[5])
    attrs[field] = value
    row[5] = attrs
    with pytest.raises(readback.NodeTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


def test_naive_utc_clickhouse_timestamp_is_supported() -> None:
    row = list(_row())
    row[6] = row[6].replace(tzinfo=None)
    row[7] = row[7].replace(tzinfo=None)
    readback.verify_trace(_window(), [tuple(row)])


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2026, 10, 25, 7, 0, 1), datetime(2026, 10, 25, 7, 0)),
        (datetime(2026, 10, 25, 7, 10), datetime(2026, 10, 25, 7, 10, 1)),
        (datetime(2026, 10, 25, 6, 50), datetime(2026, 10, 25, 6, 50, 1)),
    ],
)
def test_naive_utc_out_of_window_and_reversed_rejected(start: datetime, end: datetime) -> None:
    row = list(_row())
    row[6], row[7] = start, end
    with pytest.raises(readback.NodeTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


def test_readback_for_wrong_project_returns_no_evidence() -> None:
    client = FakeClient([])
    rows = readback.read_trace_rows(
        client, _window(), organization_id=UUID(int=3), project_id=UUID(int=4)
    )
    with pytest.raises(readback.NodeTraceNotVerified, match="Expected one"):
        readback.verify_trace(_window(), rows)


def test_invalid_trace_id_bytes_fail_safely() -> None:
    row = list(_row())
    row[0] = b"\xff" * 32
    with pytest.raises(readback.NodeTraceNotVerified, match="ASCII"):
        readback.verify_trace(_window(), [tuple(row)])
