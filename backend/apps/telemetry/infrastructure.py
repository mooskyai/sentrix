from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client

RESOURCE_KEYS = (
    "host.name",
    "k8s.cluster.name",
    "k8s.namespace.name",
    "k8s.node.name",
    "k8s.deployment.name",
    "k8s.statefulset.name",
    "k8s.daemonset.name",
    "k8s.job.name",
    "k8s.cronjob.name",
    "k8s.pod.name",
    "k8s.container.name",
)
DEFAULT_INFRASTRUCTURE_LIMIT = 100
MAX_INFRASTRUCTURE_LIMIT = 500


def _utc(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


def query_infrastructure(
    *, organization_id: UUID, project_id: UUID, start: datetime, end: datetime, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    """Return bounded co-observed OTel resource-attribute sets, never inferred inventory.

    Each grouped vector originates from one actual telemetry resource. Attribute pairs
    cannot be joined across otherwise unrelated rows, even in the same project.
    """
    if not 1 <= limit <= MAX_INFRASTRUCTURE_LIMIT:
        raise ValueError("Infrastructure limit must be between 1 and 500.")
    if start >= end:
        raise ValueError("Infrastructure time window must be ordered.")

    sources = (
        ("sentrix_metrics", "timestamp", "metric_points"),
        ("sentrix_logs", "timestamp", "log_records"),
        ("sentrix_spans", "start_time", "span_records"),
    )
    branches = []
    for table, timestamp, counter in sources:
        counts = ", ".join(
            f"toUInt64(1) AS {name}" if name == counter else f"toUInt64(0) AS {name}"
            for name in ("metric_points", "log_records", "span_records")
        )
        branches.append(
            "SELECT arrayMap(k -> trimBoth(resource_attributes[k]), "
            "{keys:Array(String)}) AS shape, "
            f"{timestamp} AS observed_at, {counts} FROM {table} "
            "WHERE organization_id = {organization_id:UUID} "
            "AND project_id = {project_id:UUID} "
            f"AND {timestamp} >= {{start:DateTime64(9)}} "
            f"AND {timestamp} < {{end:DateTime64(9)}} "
            "AND arrayExists(k -> notEmpty(trimBoth(resource_attributes[k])), "
            "{keys:Array(String)})"
        )
    sql = (
        "SELECT shape, min(observed_at) AS first_seen, max(observed_at) AS last_seen, "
        "sum(metric_points) AS metric_points, sum(log_records) AS log_records, "
        "sum(span_records) AS span_records FROM ("
        + " UNION ALL ".join(branches)
        + ") GROUP BY shape ORDER BY shape ASC "
        + f"LIMIT {limit + 1} "
        "SETTINGS max_execution_time = 8, max_rows_to_group_by = 50000, "
        "group_by_overflow_mode = 'throw'"
    )
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "start": start,
        "end": end,
        "keys": list(RESOURCE_KEYS),
    }
    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    observations = []
    for row in rows[:limit]:
        values = cast(list[str], row[0])
        attributes = {
            key: str(value)
            for key, value in zip(RESOURCE_KEYS, values, strict=True)
            if str(value).strip()
        }
        if not attributes:
            continue
        observations.append(
            {
                "attributes": attributes,
                "first_seen": _utc(cast(datetime, row[1])),
                "last_seen": _utc(cast(datetime, row[2])),
                "metric_points": int(row[3]),
                "log_records": int(row[4]),
                "span_records": int(row[5]),
            }
        )
    return observations, len(rows) > limit
