"""M6.5 read-back verifier for a known run of m6_acceptance_smoke.py.

Read-only, project-key-derived ClickHouse proof. The verifier neither sends
telemetry nor establishes separate-user or browser acceptance.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SERVICE_NAMES = ("m6-acceptance-gateway", "m6-acceptance-checkout", "m6-acceptance-payments")
ENVIRONMENT = "acceptance"
METRIC_NAME = "sentrix.m6.acceptance.requests"

_RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
_MAX_ROWS = 100
_CLUSTER = "sentrix-acceptance-cluster"


class ReadbackError(Exception):
    """Evidence missing or inconsistent; does not contain credential material."""


@dataclass(frozen=True)
class RunWindow:
    run_id: str
    trace_id: str
    start: datetime
    end: datetime


def parse_run_window(run_id: str, trace_id: str, observed_at: str) -> RunWindow:
    if not _RUN_ID.fullmatch(run_id) or not _RUN_ID.fullmatch(trace_id) or trace_id == "0" * 32:
        raise ValueError("Run ID and nonzero trace ID must each be 32 lowercase hex characters.")
    try:
        at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Timestamp must be ISO 8601 with an explicit UTC offset.") from exc
    if at.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")
    at = at.astimezone(UTC)
    # All three signals are sent within tens of milliseconds of the supplied time.
    return RunWindow(run_id, trace_id, at - timedelta(minutes=5), at + timedelta(minutes=5))


def _hex(value: Any, length: int) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            value = bytes(value).decode("ascii")
        except UnicodeDecodeError as exc:
            raise ReadbackError("Stored telemetry ID is not ASCII hexadecimal.") from exc
    normalized = str(value).rstrip("\x00").lower()
    if len(normalized) != length or any(c not in "0123456789abcdef" for c in normalized):
        raise ReadbackError("Stored telemetry ID is malformed.")
    return normalized


def read_tenant_rows(
    client: Any, evidence: RunWindow, *, organization_id: Any, project_id: Any
) -> dict[str, list[tuple[Any, ...]]]:
    columns = {
        "metrics": "service_name, environment, metric_name, number_value, resource_attributes",
        "logs": "service_name, environment, trace_id, span_id, resource_attributes",
        "spans": (
            "service_name, environment, trace_id, span_id, parent_span_id, resource_attributes"
        ),
    }
    timestamp_columns = {"metrics": "timestamp", "logs": "timestamp", "spans": "start_time"}
    result: dict[str, list[tuple[Any, ...]]] = {}
    for signal, selected in columns.items():
        table = f"sentrix_{signal}"
        timestamp = timestamp_columns[signal]
        query = (
            f"SELECT {selected} FROM {table} WHERE "
            "organization_id = {organization_id:UUID} "
            "AND project_id = {project_id:UUID} "
            f"AND {timestamp} >= {{start:DateTime64(9)}} "
            f"AND {timestamp} < {{end:DateTime64(9)}} "
            "AND resource_attributes['sentrix.acceptance.run'] = {run_id:String} "
            f"LIMIT {_MAX_ROWS + 1} SETTINGS max_execution_time = 8, "
            "max_rows_to_read = 250000, read_overflow_mode = 'throw'"
        )
        parameters = {
            "organization_id": organization_id,
            "project_id": project_id,
            "start": evidence.start,
            "end": evidence.end,
            "run_id": evidence.run_id,
        }
        rows: list[tuple[Any, ...]] = client.query(query, parameters=parameters).result_rows
        if len(rows) > _MAX_ROWS:
            raise ReadbackError(f"{signal}: read-back scan truncated; cannot certify the run.")
        result[signal] = rows
    return result


def verify_signal_rows(evidence: RunWindow, rows: dict[str, list[tuple[Any, ...]]]) -> None:
    """Check exact three-signal run evidence, per-resource labels and parentage."""
    expected = set(SERVICE_NAMES)
    span_by_service: dict[str, tuple[str, str]] = {}
    for signal in ("metrics", "logs", "spans"):
        entries = rows.get(signal, [])
        if len(entries) != 3:
            raise ReadbackError(f"{signal}: expected 3 records for the run; found {len(entries)}.")
        found: set[str] = set()
        for entry in entries:
            service, environment = str(entry[0]), str(entry[1])
            if service not in expected or service in found or environment != ENVIRONMENT:
                raise ReadbackError(
                    f"{signal}: incorrect or repeated service/environment evidence."
                )
            found.add(service)
            attrs = dict(entry[-1])
            if (
                attrs.get("sentrix.acceptance.run") != evidence.run_id
                or attrs.get("host.name") != f"sentrix-acceptance-{evidence.run_id[:12]}"
                or attrs.get("k8s.cluster.name") != _CLUSTER
                or attrs.get("k8s.namespace.name") != "sentrix-acceptance"
                or attrs.get("k8s.pod.name") != f"{service}-{evidence.run_id[:8]}"
                or attrs.get("k8s.container.name") != "app"
            ):
                raise ReadbackError(
                    f"{signal}: resource attributes do not match co-observed run labels."
                )
            if signal == "metrics":
                if entry[2] != METRIC_NAME or entry[3] is None or float(entry[3]) != 1.0:
                    raise ReadbackError("metrics: incorrect numeric sample for acceptance run.")
            elif signal == "logs":
                if _hex(entry[2], 32) != evidence.trace_id:
                    raise ReadbackError("logs: correlation trace ID differs from the run.")
            else:
                if _hex(entry[2], 32) != evidence.trace_id:
                    raise ReadbackError("spans: trace ID differs from the run.")
                span_id = _hex(entry[3], 16)
                parent_id = _hex(entry[4], 16)
                span_by_service[service] = (span_id, parent_id)
        if found != expected:
            raise ReadbackError(f"{signal}: service set does not match the producer.")

    root, checkout, payments = (span_by_service[name] for name in SERVICE_NAMES)
    if root[1] != "0" * 16 or checkout[1] != root[0] or payments[1] != checkout[0]:
        raise ReadbackError("spans: parent-child chain does not prove the expected two edges.")
    log_span_ids = {str(entry[0]): _hex(entry[3], 16) for entry in rows["logs"]}
    if any(log_span_ids[service] != span_by_service[service][0] for service in SERVICE_NAMES):
        raise ReadbackError("logs: span IDs do not correlate with service trace spans.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify stored M6 OTLP evidence for the key's project"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--time", required=True, help="UTC timestamp printed by the M6 producer")
    args = parser.parse_args()
    try:
        evidence = parse_run_window(args.run_id, args.trace_id, args.time)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.stdin.isatty():
        print("Provide the project key on stdin, never as a CLI argument.", file=sys.stderr)
        return 2
    token = sys.stdin.readline().strip()
    if not token:
        print("No project key provided on stdin.", file=sys.stderr)
        return 2

    # Django, credentials and DB connection are only needed for the operator CLI.
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
        print("Project key rejected; check expiry, revocation, and exact project.", file=sys.stderr)
        return 1
    except Exception:
        print("Project key lookup unavailable; inspect Django/PostgreSQL.", file=sys.stderr)
        return 1
    finally:
        token = ""
    if "telemetry:write" not in principal.scopes:
        print("Project key lacks telemetry:write scope.", file=sys.stderr)
        return 1
    try:
        client = get_clickhouse_client()
        try:
            rows = read_tenant_rows(
                client,
                evidence,
                organization_id=principal.organization_id,
                project_id=principal.project_id,
            )
        finally:
            client.close()
        verify_signal_rows(evidence, rows)
    except ReadbackError as exc:
        print(f"M6 read-back NOT VERIFIED: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "M6 read-back unavailable; inspect ClickHouse without exposing credentials.",
            file=sys.stderr,
        )
        return 1
    print("M6 persistence VERIFIED: three spans, logs and metric points in the key's project.")
    print(f"Project ID: {principal.project_id}")
    print(f"Run ID: {evidence.run_id}")
    print(f"Trace ID: {evidence.trace_id}")
    print("Observed relationships: gateway -> checkout -> payments (two span-parent edges).")
    print("Observed resource attributes: same recorded host/cluster and per-service pods.")
    print(
        "Foreign-user 404, browser UX, retry/teardown and external application remain UNVERIFIED."
    )
    return 0


if __name__ == "__main__":
    # Direct file execution sets sys.path[0] to /app/scripts, not the Django project root.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
