from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Gauge,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import service_catalog
from apps.telemetry.clickhouse_schema import ensure_clickhouse_schema, get_clickhouse_client
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE


class FakeQueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self, rows: list[tuple[Any, ...]], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeQueryResult:
        self.calls.append((sql, parameters))
        if self.fail:
            raise RuntimeError("unavailable raw ClickHouse credentials")
        return FakeQueryResult(self.rows)

    def close(self) -> None:
        self.closed = True


def _member_project(
    username: str, role: str = OrganizationMembership.Role.VIEWER
) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User.objects.create_user(username=f"{username}-{suffix}")
    org = Organization.objects.create(name=username, slug=f"{username}-{suffix}")
    OrganizationMembership.objects.create(user=user, organization=org, role=role)
    project = Project.objects.create(
        organization=org, name="Project", slug="project", created_by=user
    )
    return user, project


def _api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestServiceCatalogApi:
    def test_viewer_reads_observed_multi_signal_aggregate_and_tenant_parameters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project("service-catalog")
        at = datetime(2026, 10, 17, 10, 30, tzinfo=UTC)
        ch = FakeClickHouseClient(
            [
                ("checkout", "production", at, at, 2, 3, 4),
                ("logs-only", "", at, at, 0, 1, 0),
                ("metrics-only", "preview", at, at, 5, 0, 0),
                ("traces-only", "", at, at, 0, 0, 1),
            ]
        )
        monkeypatch.setattr(service_catalog, "get_clickhouse_client", lambda: ch)
        response = _api(user).get(
            f"/api/v1/projects/{project.id}/services/catalog/",
            {"start": "2026-10-17T10:00:00Z", "end": "2026-10-17T11:00:00Z"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["project_id"] == str(project.id)
        assert body["truncated"] is False
        assert body["services"][0] == {
            "service_name": "checkout",
            "environment": "production",
            "first_seen": "2026-10-17T10:30:00Z",
            "last_seen": "2026-10-17T10:30:00Z",
            "metric_points": 2,
            "log_records": 3,
            "span_records": 4,
            "signals": ["metrics", "logs", "traces"],
        }
        assert body["services"][1]["signals"] == ["logs"]
        assert body["services"][1]["environment"] == ""
        assert body["services"][2]["signals"] == ["metrics"]
        assert body["services"][3]["signals"] == ["traces"]
        assert ch.closed
        assert len(ch.calls) == 1
        sql, args = ch.calls[0]
        assert sql.count("organization_id = {organization_id:UUID}") == 3
        assert sql.count("project_id = {project_id:UUID}") == 3
        assert sql.count("service_name != ''") == 3
        assert sql.count("timestamp >= {start:DateTime64(9)}") == 2
        assert sql.count("timestamp < {end:DateTime64(9)}") == 2
        assert "start_time >= {start:DateTime64(9)}" in sql
        assert "start_time < {end:DateTime64(9)}" in sql
        assert "UNION ALL" in sql
        assert "GROUP BY service_name, environment" in sql
        assert "LIMIT 101" in sql
        assert args["organization_id"] == project.organization_id
        assert args["project_id"] == project.id
        assert args["start"] == datetime(2026, 10, 17, 10, tzinfo=UTC)
        assert args["end"] == datetime(2026, 10, 17, 11, tzinfo=UTC)

    def test_foreign_and_unknown_projects_are_not_queried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _project = _member_project("service-local")
        _other_user, foreign = _member_project("service-foreign")

        def unexpected_client() -> None:
            raise AssertionError("foreign project must not access ClickHouse")

        monkeypatch.setattr(service_catalog, "get_clickhouse_client", unexpected_client)
        client = _api(user)
        assert client.get(f"/api/v1/projects/{foreign.id}/services/catalog/").status_code == 404
        assert client.get(f"/api/v1/projects/{uuid4()}/services/catalog/").status_code == 404

    def test_anonymous_session_is_denied(self) -> None:
        _user, project = _member_project("service-unauthenticated")
        assert APIClient().get(f"/api/v1/projects/{project.id}/services/catalog/").status_code in {
            401,
            403,
        }

    def test_default_24_hour_window_and_empty_healthy_catalog(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project("service-default")
        ch = FakeClickHouseClient([])
        monkeypatch.setattr(service_catalog, "get_clickhouse_client", lambda: ch)
        before = datetime.now(UTC)
        response = _api(user).get(f"/api/v1/projects/{project.id}/services/catalog/")
        after = datetime.now(UTC)
        assert response.status_code == 200
        result = response.json()
        assert result["services"] == []
        assert result["truncated"] is False
        end = datetime.fromisoformat(result["end"].replace("Z", "+00:00"))
        start = datetime.fromisoformat(result["start"].replace("Z", "+00:00"))
        assert before <= end <= after
        assert end - start == timedelta(hours=24)
        assert ch.closed

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"start": "2026-10-17T10:00:00", "end": "2026-10-17T11:00:00Z"}, "start"),
            ({"end": "2026-10-17T11:00:00"}, "end"),
            ({"start": "bad-time"}, "start"),
            ({"start": "2026-10-17T11:00:00Z", "end": "2026-10-17T11:00:00Z"}, "start"),
            ({"start": "2026-10-09T00:00:00Z", "end": "2026-10-17T00:00:00Z"}, "start"),
            ({"limit": "0"}, "limit"),
            ({"limit": "501"}, "limit"),
            ({"limit": "abc"}, "limit"),
        ],
    )
    def test_rejects_invalid_bounds(self, params: dict[str, str], field: str) -> None:
        user, project = _member_project("service-invalid")
        response = _api(user).get(f"/api/v1/projects/{project.id}/services/catalog/", params)
        assert response.status_code == 400
        assert field in response.json()

    def test_limit_500_and_truncation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = _member_project("service-limit")
        at = datetime(2026, 10, 17, tzinfo=UTC)
        ch = FakeClickHouseClient([(f"svc-{i:04d}", "", at, at, 1, 0, 0) for i in range(501)])
        monkeypatch.setattr(service_catalog, "get_clickhouse_client", lambda: ch)
        response = _api(user).get(
            f"/api/v1/projects/{project.id}/services/catalog/", {"limit": "500"}
        )
        assert response.status_code == 200
        assert len(response.json()["services"]) == 500
        assert response.json()["truncated"] is True
        assert "LIMIT 501" in ch.calls[0][0]
        assert ch.closed

    def test_failure_returns_503_and_closes_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = _member_project("service-unavailable")
        ch = FakeClickHouseClient([], fail=True)
        monkeypatch.setattr(service_catalog, "get_clickhouse_client", lambda: ch)
        response = _api(user).get(f"/api/v1/projects/{project.id}/services/catalog/")
        assert response.status_code == 503
        assert response.json()["detail"] == "Telemetry query service is unavailable."
        assert "credentials" not in str(response.json()).lower()
        assert ch.closed


def _resource(service_name: str, environment: str) -> Resource:
    return Resource(
        attributes=[
            KeyValue(key="service.name", value=AnyValue(string_value=service_name)),
            KeyValue(key="deployment.environment.name", value=AnyValue(string_value=environment)),
        ]
    )


def _otlp_payloads(service_name: str, environment: str) -> tuple[bytes, bytes, bytes]:
    now = time.time_ns()
    metrics = ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                resource=_resource(service_name, environment),
                scope_metrics=[
                    ScopeMetrics(
                        metrics=[
                            Metric(
                                name="m6.service.catalog.integration",
                                gauge=Gauge(
                                    data_points=[NumberDataPoint(time_unix_nano=now, as_int=1)]
                                ),
                            )
                        ]
                    )
                ],
            )
        ]
    )
    logs = ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                resource=_resource(service_name, environment),
                scope_logs=[
                    ScopeLogs(
                        log_records=[
                            LogRecord(
                                time_unix_nano=now,
                                observed_time_unix_nano=now,
                                body=AnyValue(string_value="service catalog integration"),
                            )
                        ]
                    )
                ],
            )
        ]
    )
    traces = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=_resource(service_name, environment),
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=uuid4().bytes,
                                span_id=uuid4().bytes[:8],
                                name="m6.service.catalog",
                                start_time_unix_nano=now,
                                end_time_unix_nano=now + 1_000_000,
                            )
                        ]
                    )
                ],
            )
        ]
    )
    return (
        metrics.SerializeToString(),
        logs.SerializeToString(),
        traces.SerializeToString(),
    )


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_otlp_service_catalog_merges_signals_and_isolates_tenants() -> None:
    schema = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema)
    finally:
        schema.close()

    owner, project = _member_project("service-live-owner", OrganizationMembership.Role.OWNER)
    foreign_user, foreign = _member_project(
        "service-live-foreign", OrganizationMembership.Role.OWNER
    )
    local_key, local_secret = create_project_api_key(
        project=project, name="m6 catalog local", created_by=owner
    )
    foreign_key, foreign_secret = create_project_api_key(
        project=foreign, name="m6 catalog foreign", created_by=foreign_user
    )
    assert local_key.project_id == project.id
    assert foreign_key.project_id == foreign.id

    service_name = f"m6-service-{uuid4().hex}"
    ingest = APIClient()
    for token in (local_secret, foreign_secret):
        for path, body in zip(
            ("metrics", "logs", "traces"),
            _otlp_payloads(service_name, "integration"),
            strict=True,
        ):
            response = ingest.post(
                f"/v1/{path}",
                data=body,
                content_type=OTLP_PROTOBUF_CONTENT_TYPE,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            assert response.status_code == 200

    now = datetime.now(UTC)
    params = {
        "start": (now - timedelta(minutes=5)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
    }
    browser = _api(owner)
    result = browser.get(f"/api/v1/projects/{project.id}/services/catalog/", params)
    assert result.status_code == 200
    found = [
        service
        for service in result.json()["services"]
        if service["service_name"] == service_name and service["environment"] == "integration"
    ]
    assert len(found) == 1
    assert found[0]["metric_points"] == 1
    assert found[0]["log_records"] == 1
    assert found[0]["span_records"] == 1
    assert found[0]["signals"] == ["metrics", "logs", "traces"]
    assert (
        browser.get(f"/api/v1/projects/{foreign.id}/services/catalog/", params).status_code == 404
    )
