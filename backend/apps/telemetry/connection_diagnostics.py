"""Bounded, read-only observation evidence for guided project onboarding.

This endpoint reports what is stored, not collector connectivity or service health.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client

SOURCES = (
    ("metrics", "sentrix_metrics", "timestamp"),
    ("logs", "sentrix_logs", "timestamp"),
    ("traces", "sentrix_spans", "start_time"),
)


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def recent_signal_observations(
    *, organization_id: UUID, project_id: UUID, start: datetime, end: datetime
) -> dict[str, dict[str, Any]]:
    """Three budgeted, exact-tenant queries; fail on dependency errors, never fake emptiness."""
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Expected an ordered, timezone-aware observation window.")
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "start": start,
        "end": end,
    }
    client = get_clickhouse_client()
    try:
        signals: dict[str, dict[str, Any]] = {}
        for signal, table, timestamp in SOURCES:
            # Table/column names are internal constants; all caller-dependent values are typed.
            sql = (
                f"SELECT count() AS samples, max({timestamp}) AS latest "
                f"FROM {table} WHERE "
                "organization_id = {organization_id:UUID} "
                "AND project_id = {project_id:UUID} "
                f"AND {timestamp} >= {{start:DateTime64(9)}} "
                f"AND {timestamp} < {{end:DateTime64(9)}} "
                "SETTINGS max_execution_time = 8, max_rows_to_read = 250000, "
                "read_overflow_mode = 'throw'"
            )
            rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
            if len(rows) != 1 or len(rows[0]) != 2:
                raise ValueError("Unexpected telemetry query result shape.")
            count = int(rows[0][0])
            if count < 0 or (count > 0 and not isinstance(rows[0][1], datetime)):
                raise ValueError("Invalid telemetry query summary.")
            signals[signal] = {
                "observed": count > 0,
                "count": count,
                "last_seen": _utc(rows[0][1]) if count > 0 else None,
            }
        return signals
    finally:
        client.close()
