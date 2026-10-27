"""Verify one real Next.js Node SDK server span in the authenticated key's tenant.

The project/organization are derived solely from the stdin project key, never
from the command line. A successful fake receiver or OTLP HTTP 200 is not proof.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from scripts.m6_readback import RunWindow, parse_run_window

SERVICE = "m7-nextjs-node-runtime"
ENVIRONMENT = "integration"
SPAN_NAME = "m7.next.checkout"
RUN_ATTRIBUTE = "sentrix.acceptance.run"


class NextTraceNotVerified(Exception):
    """A real Next.js persistence assertion did not pass."""


def read_trace_rows(
    client: Any, window: RunWindow, *, organization_id: Any, project_id: Any
) -> list[tuple[Any, ...]]:
    sql = (
        "SELECT trace_id, span_id, span_name, span_kind, resource_attributes, "
        "attributes, start_time, end_time FROM sentrix_spans "
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
    result = client.query(
        sql,
        parameters={
            "organization_id": organization_id,
            "project_id": project_id,
            "service": SERVICE,
            "environment": ENVIRONMENT,
            "start": window.start,
            "end": window.end,
            "run_id": window.run_id,
        },
    )
    return cast(list[tuple[Any, ...]], result.result_rows)


def _hex(value: Any, length: int) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            value = bytes(value).decode("ascii")
        except UnicodeDecodeError as exc:
            raise NextTraceNotVerified("Stored span ID is invalid ASCII.") from exc
    normalized = str(value).rstrip("\x00").lower()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise NextTraceNotVerified("Stored span ID is malformed.")
    return normalized


def _utc(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise NextTraceNotVerified("Stored span timestamp is invalid.")
    # Only the queried span columns are known ClickHouse DateTime64(9, 'UTC').
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def verify_trace(window: RunWindow, rows: list[tuple[Any, ...]]) -> None:
    if len(rows) != 1:
        raise NextTraceNotVerified(f"Expected exactly one Next.js span; found {len(rows)}.")
    trace_id, span_id, name, kind, resource, attributes, started, ended = rows[0]
    if _hex(trace_id, 32) != window.trace_id or _hex(span_id, 16) == "0" * 16:
        raise NextTraceNotVerified("Next.js span ID or trace ID did not match the run.")
    if name != SPAN_NAME or type(kind) is not int or kind != 2:
        raise NextTraceNotVerified("Stored span is not the instrumented Next.js SERVER span.")
    if not isinstance(resource, dict) or not isinstance(attributes, dict):
        raise NextTraceNotVerified("Stored Next.js attributes are malformed.")
    if (
        resource.get(RUN_ATTRIBUTE) != window.run_id
        or resource.get("service.name") != SERVICE
        or resource.get("deployment.environment.name") != ENVIRONMENT
        or attributes.get(RUN_ATTRIBUTE) != window.run_id
        or attributes.get("http.request.method") != "GET"
        or attributes.get("http.route") != "/api/checkout"
    ):
        raise NextTraceNotVerified("Stored attributes do not match the Next.js HTTP request.")
    if not (window.start <= _utc(started) < _utc(ended) <= window.end):
        raise NextTraceNotVerified("Next.js span timestamps are outside the run window.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify real Next.js Node SDK span persistence")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--time", required=True)
    args = parser.parse_args()
    try:
        window = parse_run_window(args.run_id, args.trace_id, args.time)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.stdin.isatty():
        print("Supply a project key on stdin, not as a CLI argument.", file=sys.stderr)
        return 2
    token = sys.stdin.readline().strip()
    if not token:
        print("Missing temporary project key on stdin.", file=sys.stderr)
        return 2

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from rest_framework.exceptions import AuthenticationFailed

    django.setup()
    from apps.projects.authentication import authenticate_project_api_key
    from apps.telemetry.clickhouse_schema import get_clickhouse_client

    try:
        principal, _ = authenticate_project_api_key(token)
    except AuthenticationFailed:
        print("Project key rejected (invalid, expired or revoked).", file=sys.stderr)
        return 1
    except Exception:
        print("Project key lookup unavailable; inspect PostgreSQL.", file=sys.stderr)
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
    except NextTraceNotVerified as exc:
        print(f"Next.js persistence NOT VERIFIED: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Next.js read-back unavailable; inspect ClickHouse.", file=sys.stderr)
        return 1
    print("Next.js persistence VERIFIED: real App Router SERVER span in key's project.")
    print(f"Project ID: {principal.project_id}")
    print(f"Run ID: {window.run_id}")
    print(f"Trace ID: {window.trace_id}")
    print("Foreign-user, browser, revoked-key and other runtimes remain UNVERIFIED.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
