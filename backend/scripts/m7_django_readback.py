"""Verify a single isolated Django SDK trace in project-scoped ClickHouse rows."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from scripts.m6_readback import RunWindow, parse_run_window
from scripts.m7_django_runtime import ENVIRONMENT, RUN_ATTRIBUTE, SERVICE, SPAN_NAME


class DjangoTraceNotVerified(Exception):
    """Missing or mismatched durable runtime evidence."""


def read_trace_rows(
    client: Any, window: RunWindow, *, organization_id: Any, project_id: Any
) -> list[tuple[Any, ...]]:
    query = (
        "SELECT trace_id, span_id, span_name, span_kind, resource_attributes, "
        "start_time, end_time FROM sentrix_spans "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND service_name = {service:String} "
        "AND environment = {environment:String} "
        "AND start_time >= {start:DateTime64(9)} "
        "AND start_time < {end:DateTime64(9)} "
        "AND resource_attributes['sentrix.acceptance.run'] = {run_id:String} "
        "LIMIT 2 SETTINGS max_execution_time = 8, max_rows_to_read = 250000, "
        "read_overflow_mode = 'throw'"
    )
    rows = client.query(
        query,
        parameters={
            "organization_id": organization_id,
            "project_id": project_id,
            "service": SERVICE,
            "environment": ENVIRONMENT,
            "start": window.start,
            "end": window.end,
            "run_id": window.run_id,
        },
    ).result_rows
    return cast(list[tuple[Any, ...]], rows)


def _decode_id(value: Any, size: int) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("ascii")
    normalized = str(value).rstrip("\x00").lower()
    if len(normalized) != size or any(c not in "0123456789abcdef" for c in normalized):
        raise DjangoTraceNotVerified("Stored trace/span ID is malformed.")
    return normalized


def verify_trace(window: RunWindow, rows: list[tuple[Any, ...]]) -> None:
    if len(rows) != 1:
        raise DjangoTraceNotVerified(f"Expected one runtime span; found {len(rows)}.")
    trace_id, span_id, span_name, span_kind, attributes, started, ended = rows[0]
    if _decode_id(trace_id, 32) != window.trace_id or _decode_id(span_id, 16) == "0" * 16:
        raise DjangoTraceNotVerified("Runtime trace IDs do not match exporter evidence.")
    if span_name != SPAN_NAME or int(span_kind) != 2:
        raise DjangoTraceNotVerified("Runtime span is not the instrumented Django server request.")
    if dict(attributes).get(RUN_ATTRIBUTE) != window.run_id:
        raise DjangoTraceNotVerified("Runtime span does not belong to the supplied run.")
    # The schema fixes both columns to DateTime64(9, 'UTC'), but ClickHouse
    # Connect returns Python datetimes without tzinfo when the zone is UTC.
    # Interpret only these known UTC columns as UTC; never relax the window.
    if not isinstance(started, datetime) or not isinstance(ended, datetime):
        raise DjangoTraceNotVerified("Runtime span timestamp is invalid.")
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=UTC)
    if not (window.start <= started < ended <= window.end):
        raise DjangoTraceNotVerified("Runtime span timestamp is outside the evidence window.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Django SDK trace persisted in ClickHouse"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--time", required=True)
    args = parser.parse_args()
    try:
        window = parse_run_window(args.run_id, args.trace_id, args.time)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.stdin.isatty():
        print("Provide a temporary project key on stdin, not the command line.", file=sys.stderr)
        return 2
    token = sys.stdin.readline().strip()
    if not token:
        print("Missing project key on stdin.", file=sys.stderr)
        return 2

    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from rest_framework.exceptions import AuthenticationFailed

    django.setup()
    from apps.projects.authentication import authenticate_project_api_key
    from apps.telemetry.clickhouse_schema import get_clickhouse_client

    try:
        principal, _ = authenticate_project_api_key(token)
    except AuthenticationFailed:
        print("Project key rejected; check its project, expiry or revocation.", file=sys.stderr)
        return 1
    except Exception:
        print("Project key lookup unavailable; check PostgreSQL.", file=sys.stderr)
        return 1
    finally:
        token = ""
    if "telemetry:write" not in principal.scopes:
        print("Project key lacks telemetry:write scope.", file=sys.stderr)
        return 1
    try:
        client = get_clickhouse_client()
        try:
            rows = read_trace_rows(
                client,
                window,
                organization_id=principal.organization_id,
                project_id=principal.project_id,
            )
        finally:
            client.close()
        verify_trace(window, rows)
    except DjangoTraceNotVerified as exc:
        print(f"Django runtime persistence NOT VERIFIED: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Django runtime read-back unavailable; check ClickHouse.", file=sys.stderr)
        return 1
    print("Django runtime persistence VERIFIED: real Django WSGI server span in key's project.")
    print(f"Project ID: {principal.project_id}")
    print(f"Run ID: {window.run_id}")
    print(f"Trace ID: {window.trace_id}")
    print("Other framework, foreign-user and browser acceptance remain UNVERIFIED.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
