"""Bounded acceptance helper validation, without claiming live authorization proof."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.m7_node_auth_smoke import (
    AcceptanceFailed,
    _hex_id,
    _matching_server_spans,
    _utc_time,
)

TRACE = "2f06c0b95492feea6379d231993c5b5d"
RUN = "ddbaab4290524f2092254fb23ff01613"


def _response() -> dict[str, Any]:
    return {
        "truncated": False,
        "spans": [
            {
                "trace_id": TRACE,
                "service_name": "m7-node-express-runtime",
                "environment": "integration",
                "span_name": "m7.node.checkout",
                "span_kind": 2,
                "resource_attributes": {"sentrix.acceptance.run": RUN},
            }
        ],
    }


def test_exact_server_span_matches_only_correct_run_and_trace() -> None:
    response = _response()
    assert _matching_server_spans(response, TRACE, RUN) == 1
    assert _matching_server_spans(response, TRACE, "a" * 32) == 0
    assert _matching_server_spans(response, "b" * 32, RUN) == 0


def test_truncated_and_malformed_results_fail_closed() -> None:
    response = _response()
    response["truncated"] = True
    with pytest.raises(AcceptanceFailed, match="truncated"):
        _matching_server_spans(response, TRACE, RUN)
    response["truncated"] = False
    response["spans"] = [None]
    with pytest.raises(AcceptanceFailed, match="Malformed"):
        _matching_server_spans(response, TRACE, RUN)


def test_hex_rejects_nonhex_and_all_zero_ids() -> None:
    assert _hex_id(TRACE, "trace_id") == TRACE
    with pytest.raises(AcceptanceFailed):
        _hex_id("0" * 32, "trace_id")
    with pytest.raises(AcceptanceFailed):
        _hex_id("not-a-trace-id", "trace_id")


def test_timestamp_requires_utc() -> None:
    expected = datetime(2026, 10, 26, 8, 25, 53, 243000, tzinfo=UTC)
    assert _utc_time("2026-10-26T08:25:53.243Z") == expected
    with pytest.raises(AcceptanceFailed):
        _utc_time("2026-10-26T08:25:53.243")
    with pytest.raises(AcceptanceFailed):
        _utc_time("2026-10-26T08:25:53.243+05:30")
