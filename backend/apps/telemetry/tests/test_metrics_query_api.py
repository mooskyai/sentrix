from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Gauge,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import metrics_query
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
class TestMetricsQueryApi:
    def test_viewer_can_read_metric_catalog(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = _member_project(username="catalog")
        seen_at = datetime(2026, 10, 9, 4, 30, tzinfo=UTC)
        clickhouse = FakeClickHouseClient(
            [
                (
                    "http.server.duration",
                    "Request duration",
                    "ms",
                    ["histogram"],
                    ["histogram"],
                    14,
                    seen_at,
                ),
                (
                    "process.cpu.utilization",
                    "CPU utilization",
                    "1",
                    ["gauge"],
                    ["double"],
                    8,
                    seen_at,
                ),
            ]
        )
        monkeypatch.setattr(metrics_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(
            f"/api/v1/projects/{project.id}/metrics/catalog/",
            {
                "start": "2026-10-09T04:00:00Z",
                "end": "2026-10-09T05:00:00Z",
                "limit": "25",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == str(project.id)
        assert payload["metrics"][0]["supports_numeric_series"] is False
        assert payload["metrics"][1]["supports_numeric_series"] is True
        assert payload["metrics"][1]["last_seen_at"] == "2026-10-09T04:30:00Z"
        assert clickhouse.closed
        sql, parameters = clickhouse.calls[0]
        assert "organization_id = {organization_id:UUID}" in sql
        assert "project_id = {project_id:UUID}" in sql
        assert parameters["organization_id"] == project.organization_id
        assert parameters["project_id"] == project.id

    def test_foreign_project_uuid_returns_not_found_before_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _project = _member_project(username="reader")
        _foreign_user, foreign_project = _member_project(username="foreign")

        def unexpected_client() -> None:
            raise AssertionError("ClickHouse must not be queried for a foreign project")

        monkeypatch.setattr(metrics_query, "get_clickhouse_client", unexpected_client)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{foreign_project.id}/metrics/catalog/")

        assert response.status_code == 404

    def test_numeric_series_uses_bounded_filters_and_reports_truncation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="series")
        point_time = datetime(2026, 10, 9, 4, 15, tzinfo=UTC)
        clickhouse = FakeClickHouseClient(
            [
                (
                    point_time,
                    "checkout",
                    "production",
                    "gauge",
                    "",
                    0,
                    "double",
                    7.5,
                    {"route": "/checkout"},
                ),
                (
                    point_time + timedelta(seconds=1),
                    "checkout",
                    "production",
                    "gauge",
                    "",
                    0,
                    "double",
                    8.0,
                    {"route": "/checkout"},
                ),
            ]
        )
        monkeypatch.setattr(metrics_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(
            f"/api/v1/projects/{project.id}/metrics/series/",
            {
                "metric_name": "checkout.queue.depth",
                "start": "2026-10-09T04:00:00Z",
                "end": "2026-10-09T05:00:00Z",
                "service_name": "checkout",
                "environment": "production",
                "limit": "1",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["metric_name"] == "checkout.queue.depth"
        assert payload["truncated"] is True
        assert payload["points"] == [
            {
                "timestamp": "2026-10-09T04:15:00Z",
                "service_name": "checkout",
                "environment": "production",
                "metric_type": "gauge",
                "aggregation_temporality": "",
                "is_monotonic": False,
                "value_type": "double",
                "value": 7.5,
                "attributes": {"route": "/checkout"},
            }
        ]
        sql, parameters = clickhouse.calls[0]
        assert "number_value IS NOT NULL" in sql
        assert "service_name = {service_name:String}" in sql
        assert "environment = {environment:String}" in sql
        assert "LIMIT 2" in sql
        assert parameters["metric_name"] == "checkout.queue.depth"
        assert parameters["service_name"] == "checkout"
        assert parameters["environment"] == "production"
        assert clickhouse.closed

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"start": "2026-10-09T04:00:00", "end": "2026-10-09T05:00:00Z"}, "start"),
            ({"start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:01Z"}, "start"),
            ({"limit": "0"}, "limit"),
        ],
    )
    def test_catalog_rejects_invalid_query_bounds(
        self,
        params: dict[str, str],
        field: str,
    ) -> None:
        user, project = _member_project(username=f"invalid-{field}")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/metrics/catalog/", params)

        assert response.status_code == 400
        assert field in response.json()

    def test_series_requires_metric_name(self) -> None:
        user, project = _member_project(username="missing-metric")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/metrics/series/")

        assert response.status_code == 400
        assert "metric_name" in response.json()

    def test_clickhouse_failure_returns_503_and_closes_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = _member_project(username="unavailable")
        clickhouse = FakeClickHouseClient([], fail=True)
        monkeypatch.setattr(metrics_query, "get_clickhouse_client", lambda: clickhouse)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/v1/projects/{project.id}/metrics/catalog/")

        assert response.status_code == 503
        assert response.json()["detail"] == "Telemetry query service is unavailable."
        assert clickhouse.closed


def _metric_request(metric_name: str, value: int, service_name: str) -> ExportMetricsServiceRequest:
    return ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value=service_name)),
                        KeyValue(
                            key="deployment.environment.name",
                            value=AnyValue(string_value="integration"),
                        ),
                    ]
                ),
                scope_metrics=[
                    ScopeMetrics(
                        metrics=[
                            Metric(
                                name=metric_name,
                                description="M3 query integration metric",
                                unit="1",
                                gauge=Gauge(
                                    data_points=[
                                        NumberDataPoint(
                                            time_unix_nano=time.time_ns(),
                                            as_int=value,
                                            attributes=[
                                                KeyValue(
                                                    key="source",
                                                    value=AnyValue(string_value=service_name),
                                                )
                                            ],
                                        )
                                    ]
                                ),
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
        name=f"{prefix} metrics exporter",
        created_by=user,
    )
    return user, project, token


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_metric_query_is_project_scoped() -> None:
    schema_client = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema_client)
    finally:
        schema_client.close()

    user_a, project_a, token_a = _ingestion_tenant("query-a")
    _user_b, project_b, token_b = _ingestion_tenant("query-b")
    metric_name = f"sentrix.query.{uuid4().hex}"

    ingestion_client = APIClient()
    response_a = ingestion_client.post(
        "/v1/metrics",
        data=_metric_request(metric_name, 7, "query-a").SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
    )
    response_b = ingestion_client.post(
        "/v1/metrics",
        data=_metric_request(metric_name, 99, "query-b").SerializeToString(),
        content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        HTTP_AUTHORIZATION=f"Bearer {token_b}",
    )
    assert response_a.status_code == 200
    assert response_b.status_code == 200

    client = APIClient()
    client.force_authenticate(user=user_a)
    now = datetime.now(UTC)
    params = {
        "metric_name": metric_name,
        "start": (now - timedelta(minutes=5)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
    }
    series = client.get(f"/api/v1/projects/{project_a.id}/metrics/series/", params)
    foreign = client.get(f"/api/v1/projects/{project_b.id}/metrics/series/", params)

    assert series.status_code == 200
    assert [point["value"] for point in series.json()["points"]] == [7.0]
    assert foreign.status_code == 404
