from __future__ import annotations

import json
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

SMOKE_VALUE = 42.0
SERVICE_NAME = "sentrix-m3-operational-smoke"
ENVIRONMENT = "local-verification"


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


def _export_metric(token: str) -> tuple[str, str, datetime, datetime]:
    run_id = uuid4().hex
    metric_name = f"sentrix.m3.operational.smoke.{run_id}"
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
            }
        ),
        metric_readers=[reader],
    )
    meter = provider.get_meter("sentrix.m3.operational-smoke", "1.0.0")
    counter = meter.create_counter(
        metric_name,
        unit="1",
        description="Sentrix M3 operational verification metric",
    )
    counter.add(int(SMOKE_VALUE), {"sentrix.smoke.run": run_id})

    if not provider.force_flush(timeout_millis=5_000):
        provider.shutdown()
        raise SystemExit("OTLP metric exporter did not flush within the verification timeout.")
    provider.shutdown()

    finished_at = datetime.now(UTC)
    return (
        run_id,
        metric_name,
        started_at - timedelta(minutes=1),
        finished_at + timedelta(seconds=5),
    )


def _verify_metric(
    *,
    organization_id: UUID,
    project_id: UUID,
    metric_name: str,
    start: datetime,
    end: datetime,
) -> None:
    sql = (
        "SELECT count(), min(number_value), max(number_value) "
        "FROM sentrix_metrics "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND metric_name = {metric_name:String} "
        "AND service_name = {service_name:String} "
        "AND environment = {environment:String} "
        "AND timestamp >= {start:DateTime64(9)} "
        "AND timestamp < {end:DateTime64(9)} "
        "AND number_value IS NOT NULL"
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

    if not rows or int(rows[0][0]) < 1:
        raise SystemExit("Export completed but the project-scoped ClickHouse metric was not found.")
    if float(rows[0][1]) != SMOKE_VALUE or float(rows[0][2]) != SMOKE_VALUE:
        raise SystemExit("The persisted smoke metric value did not match the exported value.")


def main() -> None:
    token = _read_api_key()
    organization_id, project_id = _authenticate(token)
    run_id, metric_name, start, end = _export_metric(token)
    _verify_metric(
        organization_id=organization_id,
        project_id=project_id,
        metric_name=metric_name,
        start=start,
        end=end,
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "metric_name": metric_name,
                "service_name": SERVICE_NAME,
                "environment": ENVIRONMENT,
                "expected_value": SMOKE_VALUE,
                "start": _iso_timestamp(start),
                "end": _iso_timestamp(end),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
