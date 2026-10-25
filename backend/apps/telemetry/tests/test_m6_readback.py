"""No-secret tests for the read-only M6.5 acceptance persistence verifier."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from scripts.m6_readback import (
    METRIC_NAME,
    SERVICE_NAMES,
    ReadbackError,
    RunWindow,
    parse_run_window,
    read_tenant_rows,
    verify_signal_rows,
)

RUN_ID = "1234567890abcdef1234567890abcdef"
TRACE_ID = "aabbccddeeff00112233445566778899"
SPAN_IDS = ("1111111111111111", "2222222222222222", "3333333333333333")


def _attrs(service: str) -> dict[str, str]:
    return {
        "sentrix.acceptance.run": RUN_ID,
        "host.name": f"sentrix-acceptance-{RUN_ID[:12]}",
        "k8s.cluster.name": "sentrix-acceptance-cluster",
        "k8s.namespace.name": "sentrix-acceptance",
        "k8s.pod.name": f"{service}-{RUN_ID[:8]}",
        "k8s.container.name": "app",
    }


def _rows() -> dict[str, list[tuple[object, ...]]]:
    return {
        "metrics": [
            (service, "acceptance", METRIC_NAME, 1.0, _attrs(service)) for service in SERVICE_NAMES
        ],
        "logs": [
            (service, "acceptance", TRACE_ID.encode(), span_id.encode(), _attrs(service))
            for service, span_id in zip(SERVICE_NAMES, SPAN_IDS, strict=True)
        ],
        "spans": [
            (
                service,
                "acceptance",
                TRACE_ID.encode(),
                span_id.encode(),
                (SPAN_IDS[i - 1] if i else "0" * 16).encode(),
                _attrs(service),
            )
            for i, (service, span_id) in enumerate(zip(SERVICE_NAMES, SPAN_IDS, strict=True))
        ],
    }


def _evidence() -> RunWindow:
    return parse_run_window(RUN_ID, TRACE_ID, "2026-10-24T17:11:41.422946+00:00")


def test_validates_correlated_three_signal_persistence() -> None:
    verify_signal_rows(_evidence(), _rows())


def test_works_with_non_utc_timestamp_offset() -> None:
    evidence = parse_run_window(RUN_ID, TRACE_ID, "2026-10-24T22:41:41.422946+05:30")
    assert evidence.start == datetime(2026, 10, 24, 17, 6, 41, 422946, tzinfo=UTC)


@pytest.mark.parametrize("invalid", ["", "bad", "0" * 32, "A" * 32])
def test_rejects_unusable_trace_ids(invalid: str) -> None:
    with pytest.raises(ValueError):
        parse_run_window(RUN_ID, invalid, "2026-10-24T17:11:41Z")


def test_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        parse_run_window(RUN_ID, TRACE_ID, "2026-10-24T17:11:41")


@pytest.mark.parametrize("signal", ["metrics", "logs", "spans"])
def test_missing_signal_does_not_pass_as_empty(signal: str) -> None:
    rows = _rows()
    rows[signal] = []
    with pytest.raises(ReadbackError, match=f"{signal}: expected 3 records"):
        verify_signal_rows(_evidence(), rows)


def test_rejects_cross_trace_span() -> None:
    rows = _rows()
    span = list(rows["spans"][1])
    span[2] = ("f" * 32).encode()
    rows["spans"][1] = tuple(span)
    with pytest.raises(ReadbackError, match="trace ID differs"):
        verify_signal_rows(_evidence(), rows)


def test_rejects_invented_parent_link() -> None:
    rows = _rows()
    span = list(rows["spans"][2])
    span[4] = ("a" * 16).encode()
    rows["spans"][2] = tuple(span)
    with pytest.raises(ReadbackError, match="parent-child chain"):
        verify_signal_rows(_evidence(), rows)


def test_rejects_cross_service_resource_mixing() -> None:
    rows = _rows()
    metric = list(rows["metrics"][1])
    metric[4] = _attrs(SERVICE_NAMES[0])
    rows["metrics"][1] = tuple(metric)
    with pytest.raises(ReadbackError, match="resource attributes"):
        verify_signal_rows(_evidence(), rows)


def test_rejects_duplicate_service() -> None:
    rows = _rows()
    metric = list(rows["metrics"][1])
    metric[0] = SERVICE_NAMES[0]
    rows["metrics"][1] = tuple(metric)
    with pytest.raises(ReadbackError, match="repeated service"):
        verify_signal_rows(_evidence(), rows)


def test_read_queries_use_typed_key_derived_tenant_scope() -> None:
    fake = Mock()
    dataset = _rows()
    fake.query.side_effect = [
        SimpleNamespace(result_rows=dataset[signal]) for signal in ("metrics", "logs", "spans")
    ]
    org_id = UUID("12345678-1234-4234-8234-123456789abc")
    project_id = UUID("12345678-1234-4234-8234-123456789abd")
    actual = read_tenant_rows(fake, _evidence(), organization_id=org_id, project_id=project_id)
    assert actual == dataset
    assert fake.query.call_count == 3
    for call in fake.query.call_args_list:
        sql, params = call.args[0], call.kwargs["parameters"]
        assert "organization_id = {organization_id:UUID}" in sql
        assert "project_id = {project_id:UUID}" in sql
        assert "{run_id:String}" in sql
        assert "LIMIT 101" in sql
        assert params["organization_id"] == org_id
        assert params["project_id"] == project_id
        assert params["run_id"] == RUN_ID


def test_refuses_over_limit_result_without_claiming_persistence() -> None:
    fake = Mock()
    fake.query.return_value = SimpleNamespace(result_rows=[()] * 101)
    with pytest.raises(ReadbackError, match="truncated"):
        read_tenant_rows(fake, _evidence(), organization_id=UUID(int=1), project_id=UUID(int=2))
