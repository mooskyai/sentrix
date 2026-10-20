from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client

METRIC_NAME_LIMIT = 50
ERROR_LOG_LIMIT = 20
TRACE_REFERENCE_LIMIT = 50


def _timestamp(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _trace_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        normalized = bytes(value).decode("ascii")
    else:
        normalized = str(value)
    normalized = normalized.rstrip("\x00").lower()
    if len(normalized) != 32 or set(normalized) == {"0"}:
        return None
    if any(char not in "0123456789abcdef" for char in normalized):
        return None
    return normalized


def query_service_detail(
    *,
    organization_id: UUID,
    project_id: UUID,
    service_name: str,
    environment: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Read only bounded, exact-identity references; never infer health or lifetime presence."""
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "service_name": service_name,
        "environment": environment,
        "start": start,
        "end": end,
    }
    predicate = (
        "organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND service_name = {service_name:String} "
        "AND environment = {environment:String} "
    )
    metric_sql = (
        "SELECT metric_name, count() AS point_count FROM sentrix_metrics WHERE "
        + predicate
        + "AND timestamp >= {start:DateTime64(9)} AND timestamp < {end:DateTime64(9)} "
        "GROUP BY metric_name ORDER BY point_count DESC, metric_name ASC "
        f"LIMIT {METRIC_NAME_LIMIT + 1}"
    )
    log_sql = (
        "SELECT timestamp, severity_number, severity_text, substringUTF8(body, 1, 512), trace_id "
        "FROM sentrix_logs WHERE "
        + predicate
        + "AND timestamp >= {start:DateTime64(9)} AND timestamp < {end:DateTime64(9)} "
        "AND severity_number >= 17 "
        "ORDER BY timestamp DESC, trace_id DESC "
        f"LIMIT {ERROR_LOG_LIMIT + 1}"
    )
    trace_sql = (
        "SELECT trace_id, max(start_time) AS last_seen, count() AS span_records "
        "FROM sentrix_spans WHERE " + predicate + "AND start_time >= {start:DateTime64(9)} "
        "AND start_time < {end:DateTime64(9)} "
        "GROUP BY trace_id ORDER BY last_seen DESC, trace_id DESC "
        f"LIMIT {TRACE_REFERENCE_LIMIT + 1}"
    )

    client = get_clickhouse_client()
    try:
        metrics = cast(
            list[tuple[Any, ...]], client.query(metric_sql, parameters=parameters).result_rows
        )
        errors = cast(
            list[tuple[Any, ...]], client.query(log_sql, parameters=parameters).result_rows
        )
        traces = cast(
            list[tuple[Any, ...]], client.query(trace_sql, parameters=parameters).result_rows
        )
    finally:
        client.close()

    return {
        "metric_names": [
            {"name": str(row[0]), "point_count": int(row[1])} for row in metrics[:METRIC_NAME_LIMIT]
        ],
        "error_logs": [
            {
                "timestamp": _timestamp(cast(datetime, row[0])),
                "severity_number": int(row[1]),
                "severity_text": str(row[2]),
                "body": str(row[3]),
                "trace_id": _trace_id(row[4]),
            }
            for row in errors[:ERROR_LOG_LIMIT]
        ],
        "trace_references": [
            {
                "trace_id": _trace_id(row[0]),
                "last_seen": _timestamp(cast(datetime, row[1])),
                "span_records": int(row[2]),
            }
            for row in traces[:TRACE_REFERENCE_LIMIT]
            if _trace_id(row[0]) is not None
        ],
        "truncated": {
            "metric_names": len(metrics) > METRIC_NAME_LIMIT,
            "error_logs": len(errors) > ERROR_LOG_LIMIT,
            "trace_references": len(traces) > TRACE_REFERENCE_LIMIT,
        },
    }
