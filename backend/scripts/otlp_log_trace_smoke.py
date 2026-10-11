from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import django
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.logs.v1.logs_pb2 import SeverityNumber
from rest_framework.exceptions import AuthenticationFailed

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.projects.authentication import authenticate_project_api_key  # noqa: E402
from apps.telemetry.clickhouse_schema import get_clickhouse_client  # noqa: E402

SERVICE_NAME = "sentrix-m4-operational-smoke"
ENVIRONMENT = "local-verification"
TRACE_SCOPE_NAME = "sentrix.m4.operational-smoke"
TRACE_SCOPE_VERSION = "1.0.0"
ROOT_SPAN_NAME = "sentrix.m4.operational.root"
CHILD_SPAN_NAME = "sentrix.m4.operational.child"
EVENT_NAME = "sentrix.m4.operational.event"
ZERO_SPAN_ID = "0" * 16


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


def _new_span_id(*, exclude: str | None = None) -> str:
    while True:
        candidate = uuid4().hex[:16]
        if candidate != ZERO_SPAN_ID and candidate != exclude:
            return candidate


def _add_string_attribute(attributes: Any, key: str, value: str) -> None:
    item = attributes.add()
    item.key = key
    item.value.string_value = value


def _resource(resource: Any, run_id: str) -> None:
    _add_string_attribute(resource.attributes, "service.name", SERVICE_NAME)
    _add_string_attribute(
        resource.attributes,
        "deployment.environment.name",
        ENVIRONMENT,
    )
    _add_string_attribute(resource.attributes, "sentrix.smoke.run", run_id)


def _trace_request(
    *,
    run_id: str,
    trace_id: str,
    root_span_id: str,
    child_span_id: str,
    start_ns: int,
) -> ExportTraceServiceRequest:
    request = ExportTraceServiceRequest()
    resource_spans = request.resource_spans.add()
    _resource(resource_spans.resource, run_id)

    scope_spans = resource_spans.scope_spans.add()
    scope_spans.scope.name = TRACE_SCOPE_NAME
    scope_spans.scope.version = TRACE_SCOPE_VERSION

    root = scope_spans.spans.add()
    root.trace_id = bytes.fromhex(trace_id)
    root.span_id = bytes.fromhex(root_span_id)
    root.name = ROOT_SPAN_NAME
    root.kind = 1
    root.start_time_unix_nano = start_ns
    root.end_time_unix_nano = start_ns + 50_000_000
    root.status.code = 1
    root.flags = 1
    _add_string_attribute(root.attributes, "sentrix.smoke.run", run_id)
    _add_string_attribute(root.attributes, "sentrix.smoke.role", "root")

    child = scope_spans.spans.add()
    child.trace_id = bytes.fromhex(trace_id)
    child.span_id = bytes.fromhex(child_span_id)
    child.parent_span_id = bytes.fromhex(root_span_id)
    child.name = CHILD_SPAN_NAME
    child.kind = 3
    child.start_time_unix_nano = start_ns + 10_000_000
    child.end_time_unix_nano = start_ns + 35_000_000
    child.status.code = 2
    child.status.message = "M4 operational verification error status"
    child.flags = 1
    _add_string_attribute(child.attributes, "sentrix.smoke.run", run_id)
    _add_string_attribute(child.attributes, "sentrix.smoke.role", "child")
    _add_string_attribute(child.attributes, "http.route", "/m4-closeout")

    event = child.events.add()
    event.time_unix_nano = start_ns + 20_000_000
    event.name = EVENT_NAME
    _add_string_attribute(event.attributes, "sentrix.smoke.run", run_id)
    return request


def _log_request(
    *,
    run_id: str,
    trace_id: str,
    child_span_id: str,
    timestamp_ns: int,
    body: str,
) -> ExportLogsServiceRequest:
    request = ExportLogsServiceRequest()
    resource_logs = request.resource_logs.add()
    _resource(resource_logs.resource, run_id)

    scope_logs = resource_logs.scope_logs.add()
    scope_logs.scope.name = TRACE_SCOPE_NAME
    scope_logs.scope.version = TRACE_SCOPE_VERSION

    record = scope_logs.log_records.add()
    record.time_unix_nano = timestamp_ns
    record.observed_time_unix_nano = timestamp_ns
    record.severity_number = SeverityNumber.SEVERITY_NUMBER_ERROR
    record.severity_text = "ERROR"
    record.body.string_value = body
    record.trace_id = bytes.fromhex(trace_id)
    record.span_id = bytes.fromhex(child_span_id)
    record.flags = 1
    _add_string_attribute(record.attributes, "sentrix.smoke.run", run_id)
    _add_string_attribute(record.attributes, "http.route", "/m4-closeout")
    return request


def _send_otlp(path: str, token: str, payload: bytes) -> None:
    request = Request(
        f"http://127.0.0.1:8000{path}",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-protobuf",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise SystemExit(f"{path} returned HTTP {response.status}.")
    except HTTPError as exc:
        raise SystemExit(f"{path} returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SystemExit(f"{path} could not reach the local OTLP endpoint.") from exc


def _fixed_id(value: Any) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        normalized = bytes(value).decode("ascii")
    else:
        normalized = str(value)
    return normalized.rstrip("\x00").lower()


def _verify_spans(
    *,
    organization_id: UUID,
    project_id: UUID,
    trace_id: str,
    root_span_id: str,
    child_span_id: str,
    run_id: str,
    start: datetime,
    end: datetime,
) -> None:
    sql = (
        "SELECT span_id, parent_span_id, span_name, status_code, service_name, environment, "
        "attributes, events_json "
        "FROM sentrix_spans "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND trace_id = toFixedString({trace_id:String}, 32) "
        "AND service_name = {service_name:String} "
        "AND environment = {environment:String} "
        "AND start_time >= {start:DateTime64(9)} "
        "AND start_time < {end:DateTime64(9)} "
        "ORDER BY start_time ASC, span_id ASC "
        "LIMIT 3"
    )
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "trace_id": trace_id,
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

    if len(rows) != 2:
        raise SystemExit(
            "The project-scoped ClickHouse trace did not contain exactly two smoke spans."
        )

    by_span_id = {_fixed_id(row[0]): row for row in rows}
    root = by_span_id.get(root_span_id)
    child = by_span_id.get(child_span_id)
    if root is None or child is None:
        raise SystemExit("The persisted smoke trace did not contain the expected span IDs.")
    if _fixed_id(root[1]) != ZERO_SPAN_ID or str(root[2]) != ROOT_SPAN_NAME or int(root[3]) != 1:
        raise SystemExit("The persisted root span did not preserve root parentage/name/status.")
    if (
        _fixed_id(child[1]) != root_span_id
        or str(child[2]) != CHILD_SPAN_NAME
        or int(child[3]) != 2
    ):
        raise SystemExit("The persisted child span did not preserve parentage/name/status.")
    if str(root[4]) != SERVICE_NAME or str(child[4]) != SERVICE_NAME:
        raise SystemExit("The persisted smoke spans did not preserve service.name.")
    if str(root[5]) != ENVIRONMENT or str(child[5]) != ENVIRONMENT:
        raise SystemExit("The persisted smoke spans did not preserve the deployment environment.")
    if dict(root[6]).get("sentrix.smoke.run") != run_id:
        raise SystemExit("The persisted root span lost its smoke marker.")
    if dict(child[6]).get("sentrix.smoke.run") != run_id:
        raise SystemExit("The persisted child span lost its smoke marker.")
    if EVENT_NAME not in str(child[7]):
        raise SystemExit("The persisted child span lost its smoke event.")


def _verify_log(
    *,
    organization_id: UUID,
    project_id: UUID,
    trace_id: str,
    child_span_id: str,
    run_id: str,
    body: str,
    start: datetime,
    end: datetime,
) -> None:
    sql = (
        "SELECT trace_id, span_id, severity_number, severity_text, body, service_name, "
        "environment, "
        "attributes "
        "FROM sentrix_logs "
        "WHERE organization_id = {organization_id:UUID} "
        "AND project_id = {project_id:UUID} "
        "AND trace_id = toFixedString({trace_id:String}, 32) "
        "AND span_id = toFixedString({span_id:String}, 16) "
        "AND service_name = {service_name:String} "
        "AND environment = {environment:String} "
        "AND body = {body:String} "
        "AND timestamp >= {start:DateTime64(9)} "
        "AND timestamp < {end:DateTime64(9)} "
        "LIMIT 2"
    )
    parameters = {
        "organization_id": organization_id,
        "project_id": project_id,
        "trace_id": trace_id,
        "span_id": child_span_id,
        "service_name": SERVICE_NAME,
        "environment": ENVIRONMENT,
        "body": body,
        "start": start,
        "end": end,
    }
    client = get_clickhouse_client()
    try:
        rows = cast(list[tuple[Any, ...]], client.query(sql, parameters=parameters).result_rows)
    finally:
        client.close()

    if len(rows) != 1:
        raise SystemExit(
            "The project-scoped ClickHouse log lookup did not find exactly one smoke row."
        )
    row = rows[0]
    if _fixed_id(row[0]) != trace_id or _fixed_id(row[1]) != child_span_id:
        raise SystemExit("The persisted smoke log lost its trace/span correlation IDs.")
    if int(row[2]) != int(SeverityNumber.SEVERITY_NUMBER_ERROR) or str(row[3]) != "ERROR":
        raise SystemExit("The persisted smoke log lost its ERROR severity.")
    if str(row[4]) != body or str(row[5]) != SERVICE_NAME or str(row[6]) != ENVIRONMENT:
        raise SystemExit("The persisted smoke log lost its body/service/environment.")
    if dict(row[7]).get("sentrix.smoke.run") != run_id:
        raise SystemExit("The persisted smoke log lost its smoke marker.")


def main() -> None:
    token = _read_api_key()
    organization_id, project_id = _authenticate(token)

    run_id = uuid4().hex
    trace_id = uuid4().hex
    root_span_id = _new_span_id()
    child_span_id = _new_span_id(exclude=root_span_id)
    log_body = f"Sentrix M4 operational correlation smoke {run_id}"
    started_at = datetime.now(UTC)
    start_ns = time.time_ns()

    trace_request = _trace_request(
        run_id=run_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
        child_span_id=child_span_id,
        start_ns=start_ns,
    )
    log_request = _log_request(
        run_id=run_id,
        trace_id=trace_id,
        child_span_id=child_span_id,
        timestamp_ns=start_ns + 36_000_000,
        body=log_body,
    )

    _send_otlp("/v1/traces", token, trace_request.SerializeToString())
    _send_otlp("/v1/logs", token, log_request.SerializeToString())

    query_start = started_at - timedelta(minutes=1)
    query_end = datetime.now(UTC) + timedelta(seconds=10)
    _verify_spans(
        organization_id=organization_id,
        project_id=project_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
        child_span_id=child_span_id,
        run_id=run_id,
        start=query_start,
        end=query_end,
    )
    _verify_log(
        organization_id=organization_id,
        project_id=project_id,
        trace_id=trace_id,
        child_span_id=child_span_id,
        run_id=run_id,
        body=log_body,
        start=query_start,
        end=query_end,
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "service_name": SERVICE_NAME,
                "environment": ENVIRONMENT,
                "trace_id": trace_id,
                "root_span_id": root_span_id,
                "child_span_id": child_span_id,
                "root_span_name": ROOT_SPAN_NAME,
                "child_span_name": CHILD_SPAN_NAME,
                "event_name": EVENT_NAME,
                "log_body": log_body,
                "start": _iso_timestamp(query_start),
                "end": _iso_timestamp(query_end),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
