from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client

MAX_SERVICE_MAP_LIMIT = 500
DEFAULT_SERVICE_MAP_LIMIT = 100
MAX_SCANNED_SPANS = 10_000


def _hex_id(value: Any, length: int) -> str | None:
    """Normalize the stored ASCII FixedString IDs; reject zero/invalid IDs."""
    try:
        normalized = (
            (
                bytes(value).decode("ascii")
                if isinstance(value, (bytes, bytearray, memoryview))
                else str(value)
            )
            .rstrip("\x00")
            .lower()
        )
    except UnicodeDecodeError:
        return None
    if (
        len(normalized) != length
        or set(normalized) == {"0"}
        or any(char not in "0123456789abcdef" for char in normalized)
    ):
        return None
    return normalized


def query_service_map(
    *, organization_id: UUID, project_id: UUID, start: datetime, end: datetime, limit: int
) -> tuple[list[dict[str, Any]], bool, bool, int]:
    """Produce only observed cross-service span parent/child edges.

    A parent must be present in the same trace and tenant-bounded query window.
    Ambiguous span identities are ignored. The raw scan is intentionally capped;
    a partial scan is always reported, even when fewer than `limit` edges exist.
    """
    if not 1 <= limit <= MAX_SERVICE_MAP_LIMIT:
        raise ValueError("Service map limit must be between 1 and 500.")
    if start >= end:
        raise ValueError("Service map time window must be ordered.")

    sql = (
        "SELECT trace_id, span_id, parent_span_id, service_name, environment "
        "FROM sentrix_spans WHERE "
        "organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND start_time >= {start:DateTime64(9)} "
        "AND start_time < {end:DateTime64(9)} "
        "AND service_name != '' "
        "ORDER BY trace_id ASC, start_time ASC, span_id ASC "
        f"LIMIT {MAX_SCANNED_SPANS + 1} "
        "SETTINGS max_execution_time = 8, max_rows_to_read = 250000, "
        "read_overflow_mode = 'throw'"
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

    scan_truncated = len(rows) > MAX_SCANNED_SPANS
    rows = rows[:MAX_SCANNED_SPANS]

    # A single trace/span identity must resolve to a single service/environment.
    # Conflicting identities cannot safely establish a parent endpoint.
    identities: dict[tuple[str, str], tuple[str, str] | None] = {}
    parents: dict[tuple[str, str], str | None] = {}
    children: list[tuple[str, str, str, str, str]] = []
    for raw_trace, raw_span, raw_parent, raw_service, raw_environment in rows:
        trace_id = _hex_id(raw_trace, 32)
        span_id = _hex_id(raw_span, 16)
        if not trace_id or not span_id:
            continue
        service = str(raw_service).strip()
        if not service:
            continue
        identity = (service, str(raw_environment))
        key = (trace_id, span_id)
        parent_id = _hex_id(raw_parent, 16)
        if key not in identities:
            identities[key] = identity
            parents[key] = parent_id
        elif identities[key] != identity or parents[key] != parent_id:
            # Duplicate span IDs with conflicting service or parentage are not evidence.
            identities[key] = None
        if parent_id and parent_id != span_id:
            children.append((trace_id, span_id, parent_id, service, str(raw_environment)))

    counts: dict[tuple[str, str, str, str], int] = {}
    trace_samples: dict[tuple[str, str, str, str], list[str]] = {}
    counted: set[tuple[str, str, str]] = set()
    for trace_id, span_id, parent_id, service, environment in children:
        key = (trace_id, span_id)
        child = (service, environment)
        # Reject ambiguous child identities as well as ambiguous parents.
        if identities.get(key) != child:
            continue
        parent = identities.get((trace_id, parent_id))
        if parent is None or parent[0] == service:
            continue
        pair_id = (trace_id, span_id, parent_id)
        if pair_id in counted:
            continue
        counted.add(pair_id)
        edge = (parent[0], parent[1], service, environment)
        counts[edge] = counts.get(edge, 0) + 1
        samples = trace_samples.setdefault(edge, [])
        if trace_id not in samples and len(samples) < 3:
            samples.append(trace_id)

    ordered = sorted(counts)
    edges = [
        {
            "from_service": key[0],
            "from_environment": key[1],
            "to_service": key[2],
            "to_environment": key[3],
            "span_pairs": counts[key],
            "trace_ids": trace_samples[key],
        }
        for key in ordered[:limit]
    ]
    return edges, scan_truncated or len(ordered) > limit, scan_truncated, len(rows)
