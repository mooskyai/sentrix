from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client

MAX_SERVICE_CATALOG_LIMIT = 500


def _iso_timestamp(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def list_observed_services(
    *,
    organization_id: UUID,
    project_id: UUID,
    start: datetime,
    end: datetime,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Discover exact service/environment pairs across durable OTLP signals.

    All three signal tables have the same server-derived tenant predicates and
    half-open time window. Aggregate in ClickHouse before applying the cap so
    high-cardinality raw records cannot hide a less active service.
    """
    if not 1 <= limit <= MAX_SERVICE_CATALOG_LIMIT:
        raise ValueError("Service catalog limit must be between 1 and 500.")

    # Table identifiers, timestamp columns and LIMIT are static/validated;
    # tenant UUIDs and timestamps are typed ClickHouse parameters.
    sources = (
        ("sentrix_metrics", "timestamp", "metric_points"),
        ("sentrix_logs", "timestamp", "log_records"),
        ("sentrix_spans", "start_time", "span_records"),
    )
    selects = []
    for table, timestamp, count_column in sources:
        columns = [
            f"count() AS {name}" if name == count_column else f"toUInt64(0) AS {name}"
            for name in ("metric_points", "log_records", "span_records")
        ]
        selects.append(
            "SELECT service_name, environment, "
            f"min({timestamp}) AS first_seen, max({timestamp}) AS last_seen, "
            + ", ".join(columns)
            + f" FROM {table} "
            "WHERE organization_id = {organization_id:UUID} "
            "AND project_id = {project_id:UUID} "
            f"AND {timestamp} >= {{start:DateTime64(9)}} "
            f"AND {timestamp} < {{end:DateTime64(9)}} "
            "AND service_name != '' "
            "GROUP BY service_name, environment"
        )

    sql = (
        "SELECT service_name, environment, min(first_seen) AS first_seen, "
        "max(last_seen) AS last_seen, "
        "sum(metric_points) AS metric_points, "
        "sum(log_records) AS log_records, "
        "sum(span_records) AS span_records "
        "FROM (" + " UNION ALL ".join(selects) + ") GROUP BY service_name, environment "
        "ORDER BY service_name ASC, environment ASC "
        f"LIMIT {limit + 1}"
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

    truncated = len(rows) > limit
    services = []
    for row in rows[:limit]:
        metric_points, log_records, span_records = (int(row[4]), int(row[5]), int(row[6]))
        services.append(
            {
                "service_name": str(row[0]),
                "environment": str(row[1]),
                "first_seen": _iso_timestamp(cast(datetime, row[2])),
                "last_seen": _iso_timestamp(cast(datetime, row[3])),
                "metric_points": metric_points,
                "log_records": log_records,
                "span_records": span_records,
                "signals": [
                    name
                    for name, count in (
                        ("metrics", metric_points),
                        ("logs", log_records),
                        ("traces", span_records),
                    )
                    if count > 0
                ],
            }
        )
    return services, truncated
