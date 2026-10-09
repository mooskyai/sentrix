from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import traces_query
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


def _span_row(
    *,
    start: datetime,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    span_name: str,
    service_name: str = "checkout",
) -> tuple[Any, ...]:
    return (
        start,
        start + timedelta(milliseconds=12),
        12_000_000,
        service_name,
        "production",
        "checkout.tracer",
        "1.2.3",
        {"scope.key": "scope-value"},
        {"service.name": service_name, "region": "ap-south-1"},
        trace_id.encode("ascii"),
        span_id.encode("ascii"),
        parent_span_id.encode("ascii"),
        "vendor=value",
        span_name,
        2,
        2,
        "payment failed",
        1,
        0,
        1,
        0,
        {"http.route": "/pay"},
        '[{"name":"exception","time_unix_nano":1}]',
        "[]",
    )


@pytest.mark.django_db
class TestTraceQueryApi:
    def test_viewer_can_read_bounded_project_trace_with_raw_span_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="trace-reader")
        trace_id = "0123456789abcdef0123456789abcdef"
        root_span_id = "0123456789abcdef"
        child_span_id = "fedcba9876543210"
        start = datetime(2026, 10, 9, 6, 15, tzinfo=UTC)
        clickhouse = FakeClickHouseClient(
            [
                _span_row(
                    start=start,
                    trace_id=trace_id,
                    span_id=root_span_id,
                    parent_span_id="0" * 16,
                    span_name="POST /checkout",
                ),
                _span_row(
                    start=start + timedelta(milliseconds=2),
                    trace_id=trace_id,
                    span_id=child_span_id,
                    parent_span_id=root_span_id,
                    span_name="authorize payment",
                    service_name="payments",
                ),
                _span_row(
                    start=start + timedelta(milliseconds=4),
                    trace_id=trace_id,
                    span_id="aaaaaaaaaaaaaaaa",
                    parent_span_id=root_span_id,
                    span_name="write audit",
                ),
            ]
        )
        monkeypatch.setattr(traces_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(
            f"/api/v1/projects/{project.id}/traces/{trace_id.upper()}/",
            {
                "start": "2026-10-09T06:00:00Z",
                "end": "2026-10-09T07:00:00Z",
                "limit": "2",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == str(project.id)
        assert payload["trace_id"] == trace_id
        assert payload["truncated"] is True
        assert len(payload["spans"]) == 2
        root, child = payload["spans"]
        assert root["span_id"] == root_span_id
        assert root["parent_span_id"] is None
        assert root["span_name"] == "POST /checkout"
        assert root["duration_ns"] == 12_000_000
        assert root["status_code"] == 2
        assert root["events_json"] == '[{"name":"exception","time_unix_nano":1}]'
        assert root["resource_attributes"]["region"] == "ap-south-1"
        assert child["span_id"] == child_span_id
        assert child["parent_span_id"] == root_span_id
        assert child["service_name"] == "payments"

        sql, parameters = clickhouse.calls[0]
        assert "organization_id = {organization_id:UUID}" in sql
        assert "project_id = {project_id:UUID}" in sql
        assert "trace_id = toFixedString({trace_id:String}, 32)" in sql
        assert "start_time >= {start:DateTime64(9)}" in sql
        assert "start_time < {end:DateTime64(9)}" in sql
        assert "ORDER BY start_time ASC, span_id ASC" in sql
        assert "LIMIT 3" in sql
        assert trace_id not in sql
        assert parameters["organization_id"] == project.organization_id
        assert parameters["project_id"] == project.id
        assert parameters["trace_id"] == trace_id
        assert clickhouse.closed

    def test_foreign_project_uuid_returns_not_found_before_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _project = _member_project(username="trace-local")
        _foreign_user, foreign_project = _member_project(username="trace-foreign")

        def unexpected_client() -> None:
            raise AssertionError("ClickHouse must not be queried for a foreign project")

        monkeypatch.setattr(traces_query, "get_clickhouse_client", unexpected_client)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{foreign_project.id}/traces/{'1' * 32}/")

        assert response.status_code == 404

    @pytest.mark.parametrize("trace_id", ["not-a-trace", "0" * 32, "a" * 31, "g" * 32])
    def test_invalid_trace_id_is_rejected_without_clickhouse(
        self,
        monkeypatch: pytest.MonkeyPatch,
        trace_id: str,
    ) -> None:
        user, project = _member_project(username="trace-invalid-id")

        def unexpected_client() -> None:
            raise AssertionError("ClickHouse must not be queried for an invalid trace ID")

        monkeypatch.setattr(traces_query, "get_clickhouse_client", unexpected_client)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/traces/{trace_id}/")

        assert response.status_code == 400
        assert "trace_id" in response.json()

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"start": "2026-10-09T06:00:00", "end": "2026-10-09T07:00:00Z"}, "start"),
            ({"start": "2026-10-09T07:00:00Z", "end": "2026-10-09T07:00:00Z"}, "start"),
            ({"start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:01Z"}, "start"),
            ({"limit": "0"}, "limit"),
            ({"limit": "1001"}, "limit"),
        ],
    )
    def test_trace_lookup_rejects_invalid_bounds(
        self,
        params: dict[str, str],
        field: str,
    ) -> None:
        user, project = _member_project(username=f"trace-invalid-{field}")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/traces/{'1' * 32}/", params)

        assert response.status_code == 400
        assert field in response.json()

    def test_empty_trace_is_a_healthy_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = _member_project(username="trace-empty")
        clickhouse = FakeClickHouseClient([])
        monkeypatch.setattr(traces_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/traces/{'1' * 32}/")

        assert response.status_code == 200
        assert response.json()["spans"] == []
        assert response.json()["truncated"] is False
        assert clickhouse.closed

    def test_clickhouse_failure_returns_503_and_closes_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="trace-unavailable")
        clickhouse = FakeClickHouseClient([], fail=True)
        monkeypatch.setattr(traces_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/traces/{'1' * 32}/")

        assert response.status_code == 503
        assert response.json()["detail"] == "Telemetry query service is unavailable."
        assert clickhouse.closed


def _trace_request(
    *,
    trace_id: str,
    root_span_id: str,
    child_span_id: str,
    tenant_marker: str,
) -> ExportTraceServiceRequest:
    start = time.time_ns()
    return ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value="checkout")),
                        KeyValue(
                            key="deployment.environment.name",
                            value=AnyValue(string_value="integration"),
                        ),
                        KeyValue(
                            key="tenant.marker",
                            value=AnyValue(string_value=tenant_marker),
                        ),
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        scope=InstrumentationScope(name="sentrix.trace-test", version="1.0"),
                        spans=[
                            Span(
                                trace_id=bytes.fromhex(trace_id),
                                span_id=bytes.fromhex(root_span_id),
                                name="POST /checkout",
                                start_time_unix_nano=start,
                                end_time_unix_nano=start + 4_000_000,
                            ),
                            Span(
                                trace_id=bytes.fromhex(trace_id),
                                span_id=bytes.fromhex(child_span_id),
                                parent_span_id=bytes.fromhex(root_span_id),
                                name="authorize payment",
                                start_time_unix_nano=start + 1_000_000,
                                end_time_unix_nano=start + 3_000_000,
                            ),
                        ],
                    )
                ],
            )
        ]
    )


def _ingestion_tenant(prefix: str) -> tuple[User, Project, str]:
    user, project = _member_project(username=prefix, role=OrganizationMembership.Role.OWNER)
    _api_key, token = create_project_api_key(
        project=project,
        name=f"{prefix} trace exporter",
        created_by=user,
    )
    return user, project, token


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_trace_lookup_is_project_scoped() -> None:
    schema_client = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema_client)
    finally:
        schema_client.close()

    user_a, project_a, token_a = _ingestion_tenant("trace-query-a")
    _user_b, project_b, token_b = _ingestion_tenant("trace-query-b")
    trace_id = uuid4().hex
    root_span_id = uuid4().hex[:16]
    child_span_id = uuid4().hex[:16]

    ingestion_client = APIClient()
    response_a = ingestion_client.post(
        "/v1/traces",
        data=_trace_request(
            trace_id=trace_id,
            root_span_id=root_span_id,
            child_span_id=child_span_id,
            tenant_marker="tenant-a",
        ).SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
    )
    response_b = ingestion_client.post(
        "/v1/traces",
        data=_trace_request(
            trace_id=trace_id,
            root_span_id=root_span_id,
            child_span_id=child_span_id,
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
    }
    trace = client.get(f"/api/v1/projects/{project_a.id}/traces/{trace_id}/", params)
    foreign = client.get(f"/api/v1/projects/{project_b.id}/traces/{trace_id}/", params)

    assert trace.status_code == 200
    spans = trace.json()["spans"]
    assert len(spans) == 2
    assert {span["span_name"] for span in spans} == {"POST /checkout", "authorize payment"}
    assert {span["resource_attributes"]["tenant.marker"] for span in spans} == {"tenant-a"}
    assert foreign.status_code == 404
