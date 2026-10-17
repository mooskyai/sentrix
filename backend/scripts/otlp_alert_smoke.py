from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import django
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from rest_framework.exceptions import AuthenticationFailed

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.projects.authentication import authenticate_project_api_key  # noqa: E402
from apps.telemetry.clickhouse_schema import get_clickhouse_client  # noqa: E402

SERVICE_NAME = "sentrix-m5-operational-smoke"
ENVIRONMENT = "local-verification"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export and verify one real OTLP scalar metric for M5 operational acceptance."
    )
    parser.add_argument("--value", type=float, required=True)
    parser.add_argument("--phase", choices=("firing", "recovery"), required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--metric-name", default=None)
    return parser.parse_args()


def _read_api_key() -> str:
    token = sys.stdin.readline().strip()
    if not token:
        raise SystemExit("No project API key was provided on stdin.")
    return token


def _authenticate(token: str) -> tuple[UUID, UUID]:
    try:
        principal, _api_key = authenticate_project_api_key(token)
    except AuthenticationFailed as exc:
        raise SystemExit("Project API key was rejected.") from exc
    if "telemetry:write" not in principal.scopes:
        raise SystemExit("Project API key does not contain telemetry:write.")
    return principal.organization_id, principal.project_id


def _iso_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _export_metric(
    *,
    token: str,
    metric_name: str,
    run_id: str,
    phase: str,
    value: float,
) -> tuple[datetime, datetime]:
    started_at = datetime.now(UTC)
    exporter = OTLPMetricExporter(
        endpoint="http://127.0.0.1:8000/v1/metrics",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
    provider = MeterProvider(
        resource=Resource.create(
            {
                "service.name": SERVICE_NAME,
                "deployment.environment.name": ENVIRONMENT,
                "sentrix.smoke.run": run_id,
                "sentrix.smoke.phase": phase,
            }
        ),
        metric_readers=[reader],
    )
    meter = provider.get_meter("sentrix.m5-operational-smoke", "1.0.0")
    counter = meter.create_up_down_counter(
        metric_name,
        unit="1",
        description="Sentrix M5 operational verification metric",
    )
    counter.add(
        value,
        {
            "sentrix.smoke.run": run_id,
            "sentrix.smoke.phase": phase,
        },
    )

    if not provider.force_flush(timeout_millis=5_000):
        provider.shutdown()
        raise SystemExit("OTLP metric exporter did not flush within the verification timeout.")
    provider.shutdown()
    return started_at - timedelta(minutes=1), datetime.now(UTC) + timedelta(seconds=5)


def _verify_latest_metric(
    *,
    organization_id: UUID,
    project_id: UUID,
    metric_name: str,
    expected_value: float,
    start: datetime,
    end: datetime,
) -> datetime:
    sql = (
        "SELECT timestamp, number_value "
        "FROM sentrix_metrics "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND metric_name = {metric_name:String} "
        "AND service_name = {service_name:String} "
        "AND environment = {environment:String} "
        "AND timestamp >= {start:DateTime64(9)} "
        "AND timestamp < {end:DateTime64(9)} "
        "AND number_value IS NOT NULL "
        "ORDER BY timestamp DESC "
        "LIMIT 1"
    )
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "metric_name": metric_name,
        "service_name": SERVICE_NAME,
        "environment": ENVIRONMENT,
        "start": start,
        "end": end,
    }
    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    if not rows:
        raise SystemExit("Export completed but the project-scoped ClickHouse metric was not found.")
    timestamp, value = rows[0]
    if value is None or not math.isclose(float(value), expected_value, rel_tol=0.0, abs_tol=1e-9):
        raise SystemExit(
            "The newest persisted smoke metric value did not match the exported value."
        )
    if not isinstance(timestamp, datetime):
        raise SystemExit("The newest persisted smoke metric timestamp was invalid.")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def main() -> None:
    args = _parse_args()
    value = float(args.value)
    if not math.isfinite(value):
        raise SystemExit("Smoke metric value must be finite.")

    phase = str(args.phase)
    run_id = str(args.run_id or uuid4().hex)
    metric_name = str(args.metric_name or f"sentrix.m5.operational.smoke.{run_id}")
    token = _read_api_key()
    organization_id, project_id = _authenticate(token)
    start, end = _export_metric(
        token=token,
        metric_name=metric_name,
        run_id=run_id,
        phase=phase,
        value=value,
    )
    source_timestamp = _verify_latest_metric(
        organization_id=organization_id,
        project_id=project_id,
        metric_name=metric_name,
        expected_value=value,
        start=start,
        end=end,
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "phase": phase,
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "metric_name": metric_name,
                "service_name": SERVICE_NAME,
                "environment": ENVIRONMENT,
                "expected_value": value,
                "source_timestamp": _iso_timestamp(source_timestamp),
                "start": _iso_timestamp(start),
                "end": _iso_timestamp(end),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
