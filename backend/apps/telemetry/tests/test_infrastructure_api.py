from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
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
from apps.telemetry import infrastructure
from apps.telemetry.clickhouse_schema import ensure_clickhouse_schema, get_clickhouse_client
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE


class FakeClient:
    def __init__(self, rows: list[tuple[Any, ...]], fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def query(self, sql: str, *, parameters: dict[str, Any]) -> Any:
        self.calls.append((sql, parameters))
        if self.fail:
            raise RuntimeError("ClickHouse secret password")
        return type("Rows", (), {"result_rows": self.rows})()

    def close(self) -> None:
        self.closed = True


def member(prefix: str) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User.objects.create_user(username=f"{prefix}-{suffix}")
    org = Organization.objects.create(name=prefix, slug=f"{prefix}-{suffix}")
    OrganizationMembership.objects.create(user=user, organization=org, role="owner")
    project = Project.objects.create(organization=org, name="Test", slug="test", created_by=user)
    return user, project


def browser(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def url(project: Project) -> str:
    return f"/api/v1/projects/{project.id}/infrastructure/"


@pytest.mark.django_db
class TestInfrastructureApi:
    def test_authorization_before_clickhouse_and_genuine_foreign_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local, local_project = member("ir-local")
        _foreign, foreign_project = member("ir-foreign")

        def deny_client() -> None:
            raise AssertionError("ClickHouse must not be contacted")

        monkeypatch.setattr(infrastructure, "get_clickhouse_client", deny_client)
        assert browser(local).get(url(foreign_project)).status_code == 404
        missing = f"/api/v1/projects/{uuid4()}/infrastructure/"
        assert browser(local).get(missing).status_code == 404
        assert APIClient().get(url(local_project)).status_code in {401, 403}

    def test_exact_supported_attributes_and_three_scoped_signals(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("ir-observed")
        at = datetime(2026, 10, 22, 10, tzinfo=UTC)
        shape = [
            "host-1",
            "cluster-1",
            "payments",
            "node-a",
            "checkout",
            "",
            "",
            "",
            "",
            "checkout-01",
            "app",
        ]
        fake = FakeClient([(shape, at, at, 2, 3, 4)])
        monkeypatch.setattr(infrastructure, "get_clickhouse_client", lambda: fake)
        response = browser(user).get(
            url(project),
            {"start": "2026-10-22T09:00:00Z", "end": "2026-10-22T11:00:00Z"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["truncated"] is False
        assert result["observations"][0]["attributes"] == {
            "host.name": "host-1",
            "k8s.cluster.name": "cluster-1",
            "k8s.namespace.name": "payments",
            "k8s.node.name": "node-a",
            "k8s.deployment.name": "checkout",
            "k8s.pod.name": "checkout-01",
            "k8s.container.name": "app",
        }
        assert result["observations"][0]["metric_points"] == 2
        assert result["observations"][0]["log_records"] == 3
        assert result["observations"][0]["span_records"] == 4
        assert fake.closed
        assert len(fake.calls) == 1
        sql, args = fake.calls[0]
        assert sql.count("organization_id = {organization_id:UUID}") == 3
        assert sql.count("project_id = {project_id:UUID}") == 3
        assert "UNION ALL" in sql and "GROUP BY shape" in sql
        assert "max_rows_to_group_by = 50000" in sql
        assert "LIMIT 101" in sql
        assert args["organization_id"] == project.organization_id
        assert args["project_id"] == project.id
        assert args["keys"] == list(infrastructure.RESOURCE_KEYS)

    def test_absence_and_incomplete_observation_are_not_inventory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("ir-absence")
        at = datetime(2026, 10, 22, 10, tzinfo=UTC)
        namespace_only = ["", "", "payments"] + [""] * 8
        pod_only = ["", "", ""] + [""] * 6 + ["checkout-01", ""]
        fake = FakeClient([(namespace_only, at, at, 0, 1, 0), (pod_only, at, at, 1, 0, 0)])
        monkeypatch.setattr(infrastructure, "get_clickhouse_client", lambda: fake)
        data = browser(user).get(url(project)).json()["observations"]
        assert len(data) == 2
        assert data[0]["attributes"] == {"k8s.namespace.name": "payments"}
        assert data[1]["attributes"] == {"k8s.pod.name": "checkout-01"}
        assert not any(len(r["attributes"]) > 1 for r in data)

    @pytest.mark.parametrize(
        "params",
        [
            {"limit": "0"},
            {"limit": "501"},
            {"limit": "oops"},
            {"start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:00Z"},
            {"start": "2026-10-22T12:00:00Z", "end": "2026-10-22T12:00:00Z"},
            {"start": "2026-10-22T12:00:00"},
        ],
    )
    def test_rejects_invalid_bounds(self, params: dict[str, str]) -> None:
        user, project = member("ir-limits")
        assert browser(user).get(url(project), params).status_code == 400

    def test_default_window_empty_and_truncation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = member("ir-default")
        fake = FakeClient([])
        monkeypatch.setattr(infrastructure, "get_clickhouse_client", lambda: fake)
        result = browser(user).get(url(project)).json()
        assert result["observations"] == [] and result["truncated"] is False
        start = datetime.fromisoformat(result["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(result["end"].replace("Z", "+00:00"))
        assert end - start == timedelta(hours=24)
        at = datetime(2026, 10, 22, tzinfo=UTC)
        fake.rows = [([f"host-{i}"] + [""] * 10, at, at, 1, 0, 0) for i in range(501)]
        response = browser(user).get(url(project), {"limit": "500"})
        assert response.status_code == 200
        assert len(response.json()["observations"]) == 500
        assert response.json()["truncated"] is True
        assert "LIMIT 501" in fake.calls[-1][0]

    def test_dependency_failure_is_503_not_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = member("ir-failure")
        fake = FakeClient([], fail=True)
        monkeypatch.setattr(infrastructure, "get_clickhouse_client", lambda: fake)
        response = browser(user).get(url(project))
        assert response.status_code == 503
        assert "password" not in str(response.json())
        assert fake.closed


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_otlp_infrastructure_and_foreign_project_isolation() -> None:
    schema = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema)
    finally:
        schema.close()
    owner, project = member("ir-live")
    foreign_owner, foreign_project = member("ir-foreign-live")
    _key, token = create_project_api_key(project=project, name="infra local", created_by=owner)
    _foreign_key, foreign_token = create_project_api_key(
        project=foreign_project, name="infra foreign", created_by=foreign_owner
    )
    identifier = uuid4().hex
    attr = [
        KeyValue(key="service.name", value=AnyValue(string_value="ir-smoke")),
        KeyValue(key="host.name", value=AnyValue(string_value=f"host-{identifier}")),
        KeyValue(key="k8s.cluster.name", value=AnyValue(string_value="ir-cluster")),
        KeyValue(key="k8s.namespace.name", value=AnyValue(string_value="ir-namespace")),
        KeyValue(key="k8s.pod.name", value=AnyValue(string_value=f"pod-{identifier}")),
        KeyValue(key="k8s.container.name", value=AnyValue(string_value="app")),
        KeyValue(key="customer.internal", value=AnyValue(string_value="do-not-discover")),
    ]
    now_ns = time.time_ns()
    resource = Resource(attributes=attr)
    logs = ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                resource=resource,
                scope_logs=[
                    ScopeLogs(
                        log_records=[
                            LogRecord(
                                time_unix_nano=now_ns,
                                body=AnyValue(string_value="infra integration"),
                            )
                        ]
                    )
                ],
            )
        ]
    )
    metrics = ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                resource=resource,
                scope_metrics=[
                    ScopeMetrics(
                        metrics=[
                            Metric(
                                name="m6.infrastructure.integration",
                                gauge=Gauge(
                                    data_points=[NumberDataPoint(time_unix_nano=now_ns, as_int=1)]
                                ),
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
                resource=resource,
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=uuid4().bytes,
                                span_id=uuid4().bytes[:8],
                                name="m6.infrastructure.integration",
                                start_time_unix_nano=now_ns,
                                end_time_unix_nano=now_ns + 1_000_000,
                            )
                        ]
                    )
                ],
            )
        ]
    )
    ingest = APIClient()
    for secret in (token, foreign_token):
        for signal, payload in (
            ("logs", logs.SerializeToString()),
            ("metrics", metrics.SerializeToString()),
            ("traces", traces.SerializeToString()),
        ):
            result = ingest.post(
                f"/v1/{signal}",
                data=payload,
                content_type=OTLP_PROTOBUF_CONTENT_TYPE,
                HTTP_AUTHORIZATION=f"Bearer {secret}",
            )
            assert result.status_code == 200
    now = datetime.now(UTC)
    params = {
        "start": (now - timedelta(minutes=5)).isoformat(),
        "end": (now + timedelta(minutes=5)).isoformat(),
    }
    response = browser(owner).get(url(project), params)
    assert response.status_code == 200
    sets = [
        row["attributes"]
        for row in response.json()["observations"]
        if row["attributes"].get("host.name") == f"host-{identifier}"
    ]
    assert sets == [
        {
            "host.name": f"host-{identifier}",
            "k8s.cluster.name": "ir-cluster",
            "k8s.namespace.name": "ir-namespace",
            "k8s.pod.name": f"pod-{identifier}",
            "k8s.container.name": "app",
        }
    ]
    observed = [
        row
        for row in response.json()["observations"]
        if row["attributes"].get("host.name") == f"host-{identifier}"
    ]
    assert len(observed) == 1
    assert observed[0]["metric_points"] == 1
    assert observed[0]["log_records"] == 1
    assert observed[0]["span_records"] == 1
    assert browser(owner).get(url(foreign_project), params).status_code == 404
