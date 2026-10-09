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


def _optional_iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    return _iso_timestamp(value)


def _optional_telemetry_id(value: Any) -> str | None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        normalized = bytes(value).decode("ascii")
    else:
        normalized = str(value)
    normalized = normalized.rstrip("\x00").lower()
    if not normalized or set(normalized) == {"0"}:
        return None
    return normalized


def query_logs(
    *,
    organization_id: UUID,
    project_id: UUID,
    start: datetime,
    end: datetime,
    limit: int,
    service_name: str | None = None,
    environment: str | None = None,
    min_severity_number: int | None = None,
    body_contains: str | None = None,
    trace_id: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    filters = [
        "organization_id = {organization_id:UUID}",
        "project_id = {project_id:UUID}",
        "timestamp >= {start:DateTime64(9)}",
        "timestamp < {end:DateTime64(9)}",
    ]
    parameters: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "start": start,
        "end": end,
    }

    if service_name is not None:
        filters.append("service_name = {service_name:String}")
        parameters["service_name"] = service_name
    if environment is not None:
        filters.append("environment = {environment:String}")
        parameters["environment"] = environment
    if min_severity_number is not None:
        filters.append("severity_number >= {min_severity_number:UInt8}")
        parameters["min_severity_number"] = min_severity_number
    if body_contains is not None:
        filters.append("positionCaseInsensitiveUTF8(body, {body_contains:String}) > 0")
        parameters["body_contains"] = body_contains
    if trace_id is not None:
        filters.append("trace_id = toFixedString({trace_id:String}, 32)")
        parameters["trace_id"] = trace_id

    query_limit = limit + 1
    sql = (
        "SELECT timestamp, observed_timestamp, service_name, environment, "
        "scope_name, scope_version, "
        "scope_attributes, resource_attributes, severity_number, severity_text, body, event_name, "
        "trace_id, span_id, flags, dropped_attributes_count, attributes "
        "FROM sentrix_logs WHERE "
        + " AND ".join(filters)
        + " ORDER BY timestamp DESC, trace_id DESC, span_id DESC "
        + f"LIMIT {query_limit}"
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
                "timestamp": _iso_timestamp(row[0]),
                "observed_timestamp": _optional_iso_timestamp(row[1]),
                "service_name": str(row[2]),
                "environment": str(row[3]),
                "scope_name": str(row[4]),
                "scope_version": str(row[5]),
                "scope_attributes": dict(row[6]),
                "resource_attributes": dict(row[7]),
                "severity_number": int(row[8]),
                "severity_text": str(row[9]),
                "body": str(row[10]),
                "event_name": str(row[11]),
                "trace_id": _optional_telemetry_id(row[12]),
                "span_id": _optional_telemetry_id(row[13]),
                "flags": int(row[14]),
                "dropped_attributes_count": int(row[15]),
                "attributes": dict(row[16]),
            }
            for row in rows
        ],
        truncated,
    )
