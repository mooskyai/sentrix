from __future__ import annotations

import os
import sys
from typing import Any, cast
from uuid import UUID, uuid4

import django
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from rest_framework.exceptions import AuthenticationFailed

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.projects.authentication import authenticate_project_api_key  # noqa: E402
from apps.telemetry.clickhouse_schema import get_clickhouse_client  # noqa: E402


def _read_api_key() -> str:
    token = sys.stdin.readline().strip()
    if not token:
        raise SystemExit("No project API key was provided on stdin.")
    return token


def _authenticate(token: str) -> UUID:
    try:
        principal, _api_key = authenticate_project_api_key(token)
    except AuthenticationFailed as exc:
        raise SystemExit("Project API key was rejected.") from exc
    if "telemetry:write" not in principal.scopes:
        raise SystemExit("Project API key does not contain telemetry:write.")
    return principal.project_id


def _export_span(token: str) -> str:
    run_id = uuid4().hex
    span_name = f"sentrix-m2-smoke-{run_id}"
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "sentrix-m2-smoke",
                "deployment.environment.name": "local-verification",
                "sentrix.smoke.run": run_id,
            }
        )
    )
    exporter = OTLPSpanExporter(
        endpoint="http://127.0.0.1:8000/v1/traces",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("sentrix.m2.smoke", "1.0.0")

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("sentrix.operational_smoke", True)

    provider.shutdown()
    return span_name


def _verify_span(project_id: UUID, span_name: str) -> None:
    client = get_clickhouse_client()
    try:
        rows = cast(
            list[tuple[Any, ...]],
            client.query(
                "SELECT count() FROM sentrix_spans "
                f"WHERE project_id = toUUID('{project_id}') AND span_name = '{span_name}'"
            ).result_rows,
        )
    finally:
        client.close()

    if not rows or int(rows[0][0]) < 1:
        raise SystemExit("Export completed but the project-scoped ClickHouse span was not found.")


def main() -> None:
    token = _read_api_key()
    project_id = _authenticate(token)
    span_name = _export_span(token)
    _verify_span(project_id, span_name)
    print(f"Verified OTLP trace {span_name} for project {project_id}.")


if __name__ == "__main__":
    main()
