from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client


def _iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def _optional_telemetry_id(value: Any) -> str | None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        normalized = bytes(value).decode("ascii")
    else:
        normalized = str(value)
    normalized = normalized.rstrip("\x00").lower()
    if not normalized or set(normalized) == {"0"}:
        return None
    return normalized


def query_trace(
    *,
    organization_id: UUID,
    project_id: UUID,
    trace_id: str,
    start: datetime,
    end: datetime,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    parameters: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "trace_id": trace_id,
        "start": start,
        "end": end,
    }
    query_limit = limit + 1
    sql = (
        "SELECT start_time, end_time, duration_ns, service_name, environment, "
        "scope_name, scope_version, scope_attributes, resource_attributes, trace_id, span_id, "
        "parent_span_id, trace_state, span_name, span_kind, status_code, status_message, flags, "
        "dropped_attributes_count, dropped_events_count, dropped_links_count, attributes, "
        "events_json, links_json "
        "FROM sentrix_spans WHERE "
        "organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND trace_id = toFixedString({trace_id:String}, 32) "
        "AND start_time >= {start:DateTime64(9)} "
        "AND start_time < {end:DateTime64(9)} "
        "ORDER BY start_time ASC, span_id ASC "
        f"LIMIT {query_limit}"
    )

    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    truncated = len(rows) > limit
    rows = rows[:limit]
    return (
        [
            {
                "start_time": _iso_timestamp(row[0]),
                "end_time": _iso_timestamp(row[1]),
                "duration_ns": int(row[2]),
                "service_name": str(row[3]),
                "environment": str(row[4]),
                "scope_name": str(row[5]),
                "scope_version": str(row[6]),
                "scope_attributes": dict(row[7]),
                "resource_attributes": dict(row[8]),
                "trace_id": _optional_telemetry_id(row[9]),
                "span_id": _optional_telemetry_id(row[10]),
                "parent_span_id": _optional_telemetry_id(row[11]),
                "trace_state": str(row[12]),
                "span_name": str(row[13]),
                "span_kind": int(row[14]),
                "status_code": int(row[15]),
                "status_message": str(row[16]),
                "flags": int(row[17]),
                "dropped_attributes_count": int(row[18]),
                "dropped_events_count": int(row[19]),
                "dropped_links_count": int(row[20]),
                "attributes": dict(row[21]),
                "events_json": str(row[22]),
                "links_json": str(row[23]),
            }
            for row in rows
        ],
        truncated,
    )
