"""M7.3.3a Next.js verifier predicates; no fabricated live persistence claim."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from scripts import m7_next_readback as readback
from scripts.m6_readback import parse_run_window


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.sql = ""
        self.params: dict[str, Any] = {}

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeResult:
        self.sql = sql
        self.params = parameters
        return FakeResult(self.rows)


def _window() -> Any:
    return parse_run_window("a" * 32, "b" * 32, "2026-10-27T05:00:00Z")


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
            "http.route": "/api/checkout",
        },
        datetime(2026, 10, 27, 5, 0, tzinfo=UTC),
        datetime(2026, 10, 27, 5, 0, 0, 1000, tzinfo=UTC),
    )


def test_next_readback_scopes_to_authenticated_tenant_and_run() -> None:
    org_id, project_id = UUID(int=1), UUID(int=2)
    client = FakeClient([_row()])
    rows = readback.read_trace_rows(
        client, _window(), organization_id=org_id, project_id=project_id
    )
    readback.verify_trace(_window(), rows)
    assert client.params["organization_id"] == org_id
    assert client.params["project_id"] == project_id
    assert client.params["service"] == readback.SERVICE
    assert client.params["environment"] == readback.ENVIRONMENT
    assert client.params["run_id"] == "a" * 32
    assert "organization_id = {organization_id:UUID}" in client.sql
    assert "project_id = {project_id:UUID}" in client.sql
    assert "resource_attributes['sentrix.acceptance.run'] = {run_id:String}" in client.sql
    assert "LIMIT 2" in client.sql
    assert "max_execution_time = 8" in client.sql
    assert "max_rows_to_read = 250000" in client.sql


@pytest.mark.parametrize("rows", [[], [_row(), _row()]])
def test_rejects_missing_and_duplicate_spans(rows: list[tuple[Any, ...]]) -> None:
    with pytest.raises(readback.NextTraceNotVerified):
        readback.verify_trace(_window(), rows)


@pytest.mark.parametrize(
    "index,replacement",
    [
        (0, "f" * 32),
        (1, "0" * 16),
        (2, "unrelated.span"),
        (3, "2"),
        (3, 1),
        (4, {readback.RUN_ATTRIBUTE: "wrong"}),
        (5, {readback.RUN_ATTRIBUTE: "wrong"}),
        (6, "not a datetime"),
        (7, None),
    ],
)
def test_rejects_mismatched_and_malformed_evidence(index: int, replacement: Any) -> None:
    row = list(_row())
    row[index] = replacement
    with pytest.raises(readback.NextTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


@pytest.mark.parametrize(
    "field,value",
    [
        ("sentrix.acceptance.run", "invalid"),
        ("http.request.method", "POST"),
        ("http.route", "/wrong"),
    ],
)
def test_wrong_http_identity_never_passes(field: str, value: str) -> None:
    row = list(_row())
    attrs = dict(row[5])
    attrs[field] = value
    row[5] = attrs
    with pytest.raises(readback.NextTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


def test_utc_naive_timestamps_from_known_clickhouse_columns_pass() -> None:
    row = list(_row())
    row[6] = row[6].replace(tzinfo=None)
    row[7] = row[7].replace(tzinfo=None)
    readback.verify_trace(_window(), [tuple(row)])


def test_wrong_project_readback_is_not_evidence() -> None:
    client = FakeClient([])
    rows = readback.read_trace_rows(
        client, _window(), organization_id=UUID(int=3), project_id=UUID(int=4)
    )
    with pytest.raises(readback.NextTraceNotVerified, match="exactly one"):
        readback.verify_trace(_window(), rows)


def test_invalid_trace_id_bytes_rejected() -> None:
    row = list(_row())
    row[0] = b"\xff" * 32
    with pytest.raises(readback.NextTraceNotVerified, match="ASCII"):
        readback.verify_trace(_window(), [tuple(row)])
