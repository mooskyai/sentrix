from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs, SeverityNumber
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import logs_query
from apps.telemetry.clickhouse_schema import ensure_clickhouse_schema, get_clickhouse_client
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE


class FakeQueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self, rows: list[tuple[Any, ...]], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.closed = False
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeQueryResult:
        self.calls.append((sql, parameters))
        if self.fail:
            raise RuntimeError("clickhouse unavailable")
        return FakeQueryResult(self.rows)

    def close(self) -> None:
        self.closed = True


def _member_project(
    *,
    username: str,
    role: str = OrganizationMembership.Role.VIEWER,
) -> tuple[User, Project]:
    unique = uuid4().hex[:10]
    user = User.objects.create_user(username=f"{username}-{unique}")
    organization = Organization.objects.create(
        name=f"{username} organization",
        slug=f"{username}-{unique}",
    )
    OrganizationMembership.objects.create(organization=organization, user=user, role=role)
    project = Project.objects.create(
        organization=organization,
        name=f"{username} project",
        slug=f"{username}-{unique}",
        created_by=user,
    )
    return user, project


@pytest.mark.django_db
class TestLogsQueryApi:
    def test_viewer_can_search_logs_with_bounded_typed_filters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="logs")
        timestamp = datetime(2026, 10, 9, 6, 15, tzinfo=UTC)
        observed = timestamp + timedelta(milliseconds=5)
        trace_id = "0123456789abcdef0123456789abcdef"
        span_id = "0123456789abcdef"
        clickhouse = FakeClickHouseClient(
            [
                (
                    timestamp,
                    observed,
                    "checkout",
                    "production",
                    "checkout.logger",
                    "1.0.0",
                    {"scope": "value"},
                    {"service.name": "checkout"},
                    17,
                    "ERROR",
                    "Payment FAILED for order 42",
                    "payment.failed",
                    trace_id.encode("ascii"),
                    span_id.encode("ascii"),
                    1,
                    0,
                    {"order.id": "42"},
                ),
                (
                    timestamp - timedelta(seconds=1),
                    None,
                    "checkout",
                    "production",
                    "checkout.logger",
                    "1.0.0",
                    {},
                    {"service.name": "checkout"},
                    13,
                    "WARN",
                    "Payment retry",
                    "",
                    trace_id.encode("ascii"),
                    span_id.encode("ascii"),
                    0,
                    0,
                    {},
                ),
            ]
        )
        monkeypatch.setattr(logs_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)
        body_filter = "FAILED' OR 1=1 --"

        response = client.get(
            f"/api/v1/projects/{project.id}/logs/search/",
            {
                "start": "2026-10-09T06:00:00Z",
                "end": "2026-10-09T07:00:00Z",
                "service_name": "checkout",
                "environment": "production",
                "min_severity_number": "13",
                "body_contains": body_filter,
                "trace_id": trace_id.upper(),
                "limit": "1",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == str(project.id)
        assert payload["truncated"] is True
        assert payload["filters"] == {
            "service_name": "checkout",
            "environment": "production",
            "min_severity_number": 13,
            "body_contains": body_filter,
            "trace_id": trace_id,
        }
        assert payload["logs"] == [
            {
                "timestamp": "2026-10-09T06:15:00Z",
                "observed_timestamp": "2026-10-09T06:15:00.005000Z",
                "service_name": "checkout",
                "environment": "production",
                "scope_name": "checkout.logger",
                "scope_version": "1.0.0",
                "scope_attributes": {"scope": "value"},
                "resource_attributes": {"service.name": "checkout"},
                "severity_number": 17,
                "severity_text": "ERROR",
                "body": "Payment FAILED for order 42",
                "event_name": "payment.failed",
                "trace_id": trace_id,
                "span_id": span_id,
                "flags": 1,
                "dropped_attributes_count": 0,
                "attributes": {"order.id": "42"},
            }
        ]

        sql, parameters = clickhouse.calls[0]
        assert "organization_id = {organization_id:UUID}" in sql
        assert "project_id = {project_id:UUID}" in sql
        assert "service_name = {service_name:String}" in sql
        assert "environment = {environment:String}" in sql
        assert "severity_number >= {min_severity_number:UInt8}" in sql
        assert "positionCaseInsensitiveUTF8(body, {body_contains:String}) > 0" in sql
        assert "trace_id = toFixedString({trace_id:String}, 32)" in sql
        assert "LIMIT 2" in sql
        assert body_filter not in sql
        assert parameters["organization_id"] == project.organization_id
        assert parameters["project_id"] == project.id
        assert parameters["body_contains"] == body_filter
        assert parameters["trace_id"] == trace_id
        assert clickhouse.closed

    def test_foreign_project_uuid_returns_not_found_before_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _project = _member_project(username="logs-reader")
        _foreign_user, foreign_project = _member_project(username="logs-foreign")

        def unexpected_client() -> None:
            raise AssertionError("ClickHouse must not be queried for a foreign project")

        monkeypatch.setattr(logs_query, "get_clickhouse_client", unexpected_client)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{foreign_project.id}/logs/search/")

        assert response.status_code == 404

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"start": "2026-10-09T06:00:00", "end": "2026-10-09T07:00:00Z"}, "start"),
            ({"start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:01Z"}, "start"),
            ({"limit": "0"}, "limit"),
            ({"limit": "1001"}, "limit"),
            ({"min_severity_number": "25"}, "min_severity_number"),
            ({"trace_id": "not-a-trace-id"}, "trace_id"),
            ({"trace_id": "0" * 32}, "trace_id"),
        ],
    )
    def test_search_rejects_invalid_query_bounds(
        self,
        params: dict[str, str],
        field: str,
    ) -> None:
        user, project = _member_project(username=f"logs-invalid-{field}")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/logs/search/", params)

        assert response.status_code == 400
        assert field in response.json()

    def test_zero_storage_ids_are_returned_as_uncorrelated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="logs-uncorrelated")
        timestamp = datetime(2026, 10, 9, 6, 15, tzinfo=UTC)
        clickhouse = FakeClickHouseClient(
            [
                (
                    timestamp,
                    None,
                    "worker",
                    "local",
                    "",
                    "",
                    {},
                    {},
                    9,
                    "INFO",
                    "background task complete",
                    "",
                    ("0" * 32).encode("ascii"),
                    ("0" * 16).encode("ascii"),
                    0,
                    0,
                    {},
                )
            ]
        )
        monkeypatch.setattr(logs_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/logs/search/")

        assert response.status_code == 200
        assert response.json()["logs"][0]["trace_id"] is None
        assert response.json()["logs"][0]["span_id"] is None

    def test_clickhouse_failure_returns_503_and_closes_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="logs-unavailable")
        clickhouse = FakeClickHouseClient([], fail=True)
        monkeypatch.setattr(logs_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/logs/search/")

        assert response.status_code == 503
        assert response.json()["detail"] == "Telemetry query service is unavailable."
        assert clickhouse.closed


def _log_request(
    *,
    body: str,
    trace_id: str,
    span_id: str,
    tenant_marker: str,
) -> ExportLogsServiceRequest:
    now = time.time_ns()
    return ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value="checkout")),
                        KeyValue(
                            key="deployment.environment.name",
                            value=AnyValue(string_value="integration"),
                        ),
                    ]
                ),
                scope_logs=[
                    ScopeLogs(
                        log_records=[
                            LogRecord(
                                time_unix_nano=now,
                                observed_time_unix_nano=now,
                                severity_number=SeverityNumber.SEVERITY_NUMBER_ERROR,
                                severity_text="ERROR",
                                body=AnyValue(string_value=body),
                                trace_id=bytes.fromhex(trace_id),
                                span_id=bytes.fromhex(span_id),
                                attributes=[
                                    KeyValue(
                                        key="tenant.marker",
                                        value=AnyValue(string_value=tenant_marker),
                                    )
                                ],
                            )
                        ]
                    )
                ],
            )
        ]
    )


def _ingestion_tenant(prefix: str) -> tuple[User, Project, str]:
    user, project = _member_project(username=prefix, role=OrganizationMembership.Role.OWNER)
    _api_key, token = create_project_api_key(
        project=project,
        name=f"{prefix} logs exporter",
        created_by=user,
    )
    return user, project, token


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_log_search_is_project_scoped() -> None:
    schema_client = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema_client)
    finally:
        schema_client.close()

    user_a, project_a, token_a = _ingestion_tenant("logs-query-a")
    _user_b, project_b, token_b = _ingestion_tenant("logs-query-b")
    unique = uuid4().hex
    body = f"sentrix M4 isolation failure {unique}"
    trace_id = uuid4().hex
    span_id = uuid4().hex[:16]

    ingestion_client = APIClient()
    response_a = ingestion_client.post(
        "/v1/logs",
        data=_log_request(
            body=body,
            trace_id=trace_id,
            span_id=span_id,
            tenant_marker="tenant-a",
        ).SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
    )
    response_b = ingestion_client.post(
        "/v1/logs",
        data=_log_request(
            body=body,
            trace_id=trace_id,
            span_id=span_id,
            tenant_marker="tenant-b",
        ).SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token_b}",
    )
    assert response_a.status_code == 200
    assert response_b.status_code == 200

    client = APIClient()
    client.force_authenticate(user=user_a)
    now = datetime.now(UTC)
    params = {
        "start": (now - timedelta(minutes=5)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
        "service_name": "checkout",
        "environment": "integration",
        "body_contains": unique,
        "trace_id": trace_id,
    }
    search = client.get(f"/api/v1/projects/{project_a.id}/logs/search/", params)
    foreign = client.get(f"/api/v1/projects/{project_b.id}/logs/search/", params)

    assert search.status_code == 200
    logs = search.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["body"] == body
    assert logs[0]["trace_id"] == trace_id
    assert logs[0]["attributes"]["tenant.marker"] == "tenant-a"
    assert foreign.status_code == 404
