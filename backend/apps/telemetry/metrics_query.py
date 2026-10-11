from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client


class AmbiguousLatestMetricPoint(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LatestNumericMetricPoint:
    timestamp: datetime
    value: float


def _utc_datetime(value: datetime) -> datetime:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC)


def _iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def list_metric_catalog(
    *,
    organization_id: UUID,
    project_id: UUID,
    start: datetime,
    end: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    sql = (
        "SELECT metric_name, "
        "argMax(metric_description, timestamp), "
        "argMax(metric_unit, timestamp), "
        "arraySort(groupUniqArray(metric_type)), "
        "arraySort(groupUniqArray(value_type)), "
        "count(), max(timestamp) "
        "FROM sentrix_metrics "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND timestamp >= {start:DateTime64(9)} "
        "AND timestamp < {end:DateTime64(9)} "
        "GROUP BY metric_name "
        "ORDER BY metric_name ASC "
        f"LIMIT {limit}"
    )
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "start": start,
        "end": end,
    }
    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    return [
        {
            "name": str(row[0]),
            "description": str(row[1]),
            "unit": str(row[2]),
            "metric_types": [str(value) for value in row[3]],
            "value_types": [str(value) for value in row[4]],
            "supports_numeric_series": bool({"int", "double"}.intersection(row[4])),
            "point_count": int(row[5]),
            "last_seen_at": _iso_timestamp(row[6]),
        }
        for row in rows
    ]


def query_numeric_metric_series(
    *,
    organization_id: UUID,
    project_id: UUID,
    metric_name: str,
    start: datetime,
    end: datetime,
    limit: int,
    service_name: str | None = None,
    environment: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    filters = [
        "organization_id = {organization_id:UUID}",
        "project_id = {project_id:UUID}",
        "metric_name = {metric_name:String}",
        "timestamp >= {start:DateTime64(9)}",
        "timestamp < {end:DateTime64(9)}",
        "number_value IS NOT NULL",
    ]
    parameters: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "metric_name": metric_name,
        "start": start,
        "end": end,
    }
    if service_name is not None:
        filters.append("service_name = {service_name:String}")
        parameters["service_name"] = service_name
    if environment is not None:
        filters.append("environment = {environment:String}")
        parameters["environment"] = environment

    query_limit = limit + 1
    sql = (
        "SELECT timestamp, service_name, environment, metric_type, "
        "aggregation_temporality, is_monotonic, value_type, number_value, attributes "
        "FROM sentrix_metrics WHERE "
        + " AND ".join(filters)
        + " ORDER BY timestamp ASC "
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
                "service_name": str(row[1]),
                "environment": str(row[2]),
                "metric_type": str(row[3]),
                "aggregation_temporality": str(row[4]),
                "is_monotonic": bool(row[5]),
                "value_type": str(row[6]),
                "value": float(row[7]),
                "attributes": dict(row[8]),
            }
            for row in rows
        ],
        truncated,
    )


def query_latest_numeric_metric_point(
    *,
    organization_id: UUID,
    project_id: UUID,
    metric_name: str,
    start: datetime,
    end: datetime,
    service_name: str | None = None,
    environment: str | None = None,
) -> LatestNumericMetricPoint | None:
    filters = [
        "organization_id = {organization_id:UUID}",
        "project_id = {project_id:UUID}",
        "metric_name = {metric_name:String}",
        "timestamp >= {start:DateTime64(9)}",
        "timestamp < {end:DateTime64(9)}",
        "number_value IS NOT NULL",
    ]
    parameters: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "metric_name": metric_name,
        "start": start,
        "end": end,
    }
    if service_name is not None:
        filters.append("service_name = {service_name:String}")
        parameters["service_name"] = service_name
    if environment is not None:
        filters.append("environment = {environment:String}")
        parameters["environment"] = environment

    sql = (
        "SELECT timestamp, number_value "
        "FROM sentrix_metrics WHERE " + " AND ".join(filters) + " ORDER BY timestamp DESC LIMIT 2"
    )
    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    if not rows:
        return None

    latest_timestamp = _utc_datetime(cast(datetime, rows[0][0]))
    if len(rows) > 1 and _utc_datetime(cast(datetime, rows[1][0])) == latest_timestamp:
        raise AmbiguousLatestMetricPoint(
            "More than one numeric metric point shares the latest timestamp."
        )

    return LatestNumericMetricPoint(
        timestamp=latest_timestamp,
        value=float(rows[0][1]),
    )
