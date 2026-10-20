from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.telemetry import service_detail


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, outputs: list[list[tuple[Any, ...]]], *, fail_at: int = 0) -> None:
        self.outputs = outputs
        self.fail_at = fail_at
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeResult:
        self.calls.append((sql, parameters))
        if self.fail_at == len(self.calls):
            raise RuntimeError("raw internal ClickHouse error: password=secret")
        return FakeResult(self.outputs[len(self.calls) - 1])

    def close(self) -> None:
        self.closed = True


def member(username: str, role: str = OrganizationMembership.Role.VIEWER) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User.objects.create_user(username=f"{username}-{suffix}")
    organization = Organization.objects.create(name=username, slug=f"{username}-{suffix}")
    OrganizationMembership.objects.create(organization=organization, user=user, role=role)
    project = Project.objects.create(
        organization=organization, name="Project", slug="project", created_by=user
    )
    return user, project


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def url(project: Project) -> str:
    return f"/api/v1/projects/{project.id}/services/detail/"


PARAMS = {
    "service_name": "checkout",
    "environment": "",
    "start": "2026-10-17T10:00:00Z",
    "end": "2026-10-17T11:00:00Z",
}


@pytest.mark.django_db
class TestServiceDetailApi:
    def test_exact_empty_environment_and_tenant_predicates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("detail-exact")
        at = datetime(2026, 10, 17, 10, 30, tzinfo=UTC)
        trace = "a" * 32
        ch = FakeClient(
            [
                [("requests", 9)],
                [(at, 17, "ERROR", "failed request", trace.encode("ascii"))],
                [(trace.encode("ascii"), at, 2)],
            ]
        )
        monkeypatch.setattr(service_detail, "get_clickhouse_client", lambda: ch)
        response = client_for(user).get(url(project), PARAMS)
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == str(project.id)
        assert data["service_name"] == "checkout"
        assert data["environment"] == ""
        assert data["metric_names"] == [{"name": "requests", "point_count": 9}]
        assert data["error_logs"][0]["trace_id"] == trace
        assert data["trace_references"] == [
            {"trace_id": trace, "last_seen": "2026-10-17T10:30:00Z", "span_records": 2}
        ]
        assert data["truncated"] == {
            "metric_names": False,
            "error_logs": False,
            "trace_references": False,
        }
        assert ch.closed and len(ch.calls) == 3
        for sql, args in ch.calls:
            assert "organization_id = {organization_id:UUID}" in sql
            assert "project_id = {project_id:UUID}" in sql
            assert "service_name = {service_name:String}" in sql
            assert "environment = {environment:String}" in sql
            assert "{start:DateTime64(9)}" in sql
            assert "{end:DateTime64(9)}" in sql
            assert args["organization_id"] == project.organization_id
            assert args["project_id"] == project.id
            assert args["service_name"] == "checkout"
            assert args["environment"] == ""
        assert "severity_number >= 17" in ch.calls[1][0]
        assert "GROUP BY trace_id" in ch.calls[2][0]

    def test_empty_is_not_dependency_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = member("detail-empty")
        ch = FakeClient([[], [], []])
        monkeypatch.setattr(service_detail, "get_clickhouse_client", lambda: ch)
        response = client_for(user).get(url(project), PARAMS)
        assert response.status_code == 200
        assert response.json()["metric_names"] == []
        assert response.json()["error_logs"] == []
        assert response.json()["trace_references"] == []
        assert ch.closed

    def test_truncation_is_independent_for_each_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("detail-truncation")
        at = datetime(2026, 10, 17, 10, 30, tzinfo=UTC)
        ch = FakeClient(
            [
                [(f"metric-{i}", 1) for i in range(service_detail.METRIC_NAME_LIMIT + 1)],
                [
                    (at, 17, "ERROR", "e", "b" * 32)
                    for _ in range(service_detail.ERROR_LOG_LIMIT + 1)
                ],
                [("c" * 32, at, 1) for _ in range(service_detail.TRACE_REFERENCE_LIMIT + 1)],
            ]
        )
        monkeypatch.setattr(service_detail, "get_clickhouse_client", lambda: ch)
        data = client_for(user).get(url(project), PARAMS).json()
        assert len(data["metric_names"]) == service_detail.METRIC_NAME_LIMIT
        assert len(data["error_logs"]) == service_detail.ERROR_LOG_LIMIT
        assert len(data["trace_references"]) == service_detail.TRACE_REFERENCE_LIMIT
        assert all(data["truncated"].values())

    def test_foreign_project_is_404_before_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _ = member("detail-owner")
        _, foreign = member("detail-foreign")

        def unexpected_client() -> None:
            raise AssertionError("ClickHouse must not be accessed for foreign tenants")

        monkeypatch.setattr(service_detail, "get_clickhouse_client", unexpected_client)
        client = client_for(user)
        assert client.get(url(foreign), PARAMS).status_code == 404
        assert client.get(f"/api/v1/projects/{uuid4()}/services/detail/", PARAMS).status_code == 404

    def test_requires_authenticated_session(self) -> None:
        _, project = member("detail-anonymous")
        assert APIClient().get(url(project), PARAMS).status_code in {401, 403}

    @pytest.mark.parametrize(
        ("changes", "field"),
        [
            ({"service_name": ""}, "service_name"),
            ({"service_name": "x" * 513}, "service_name"),
            ({"environment": "x" * 513}, "environment"),
            ({"start": "2026-10-17T10:00:00"}, "start"),
            ({"start": "2026-10-17T11:00:00Z"}, "start"),
            ({"start": "2026-10-01T11:00:00Z"}, "start"),
        ],
    )
    def test_invalid_query_is_400(self, changes: dict[str, str], field: str) -> None:
        user, project = member("detail-invalid")
        response = client_for(user).get(url(project), {**PARAMS, **changes})
        assert response.status_code == 400
        assert field in response.json()

    def test_missing_environment_is_not_coerced_to_empty(self) -> None:
        user, project = member("detail-missing-env")
        request = {key: value for key, value in PARAMS.items() if key != "environment"}
        response = client_for(user).get(url(project), request)
        assert response.status_code == 400
        assert "environment" in response.json()

    def test_query_failure_is_503_and_client_is_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("detail-failure")
        ch = FakeClient([[], [], []], fail_at=2)
        monkeypatch.setattr(service_detail, "get_clickhouse_client", lambda: ch)
        response = client_for(user).get(url(project), PARAMS)
        assert response.status_code == 503
        assert "password" not in str(response.json())
        assert ch.closed


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_detail_uses_exact_project_service_and_environment() -> None:
    from datetime import timedelta

    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue
    from opentelemetry.proto.logs.v1 import logs_pb2
    from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs

    from apps.projects.services import create_project_api_key
    from apps.telemetry.clickhouse_schema import ensure_clickhouse_schema, get_clickhouse_client
    from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE
    from apps.telemetry.tests.test_service_catalog_api import _otlp_payloads, _resource

    ch = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(ch)
    finally:
        ch.close()

    owner, project = member("detail-live", OrganizationMembership.Role.OWNER)
    foreign_user, foreign = member("detail-live-foreign", OrganizationMembership.Role.OWNER)
    _, local_secret = create_project_api_key(
        project=project, name="m6 detail local", created_by=owner
    )
    _, foreign_secret = create_project_api_key(
        project=foreign, name="m6 detail foreign", created_by=foreign_user
    )
    service_name = f"m6-detail-{uuid4().hex}"
    body = f"detail-error-{uuid4().hex}"
    ingest = APIClient()
    for token in (local_secret, foreign_secret):
        for signal, payload in zip(
            ("metrics", "logs", "traces"),
            _otlp_payloads(service_name, ""),
            strict=True,
        ):
            result = ingest.post(
                f"/v1/{signal}",
                data=payload,
                content_type=OTLP_PROTOBUF_CONTENT_TYPE,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            assert result.status_code == 200

    from time import time_ns

    at = time_ns()
    error_payload = ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                resource=_resource(service_name, ""),
                scope_logs=[
                    ScopeLogs(
                        log_records=[
                            LogRecord(
                                time_unix_nano=at,
                                observed_time_unix_nano=at,
                                severity_number=logs_pb2.SEVERITY_NUMBER_ERROR,
                                severity_text="ERROR",
                                body=AnyValue(string_value=body),
                            )
                        ]
                    )
                ],
            )
        ]
    )
    result = ingest.post(
        "/v1/logs",
        data=error_payload.SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {local_secret}",
    )
    assert result.status_code == 200

    now = datetime.now(UTC)
    params = {
        "service_name": service_name,
        "environment": "",
        "start": (now - timedelta(minutes=5)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
    }
    browser = client_for(owner)
    response = browser.get(url(project), params)
    assert response.status_code == 200
    detail = response.json()
    assert detail["environment"] == ""
    metric = next(
        item for item in detail["metric_names"] if item["name"] == "m6.service.catalog.integration"
    )
    assert metric["point_count"] == 1  # Excludes the foreign project's same-named point.
    assert any(log["body"] == body for log in detail["error_logs"])
    assert len(detail["trace_references"]) == 1
    assert browser.get(url(foreign), params).status_code == 404
