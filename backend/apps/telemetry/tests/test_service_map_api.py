from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry import service_map
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
            raise RuntimeError("secret ClickHouse credentials")
        return type("Rows", (), {"result_rows": self.rows})()

    def close(self) -> None:
        self.closed = True


def member(prefix: str) -> tuple[User, Project]:
    suffix = uuid4().hex[:10]
    user = User.objects.create_user(username=f"{prefix}-{suffix}")
    org = Organization.objects.create(name=prefix, slug=f"{prefix}-{suffix}")
    OrganizationMembership.objects.create(user=user, organization=org, role="viewer")
    project = Project.objects.create(organization=org, name="Test", slug="test", created_by=user)
    return user, project


def browser(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def path(project: Project) -> str:
    return f"/api/v1/projects/{project.id}/services/map/"


def span(
    trace: str, identity: str, parent: str, service: str, env: str = ""
) -> tuple[str, str, str, str, str]:
    return (trace, identity, parent, service, env)


@pytest.mark.django_db
class TestServiceMapApi:
    def test_membership_before_clickhouse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        local, project = member("map-local")
        _other, foreign = member("map-foreign")

        def forbidden() -> None:
            raise AssertionError("Unauthorized user must not reach ClickHouse")

        monkeypatch.setattr(service_map, "get_clickhouse_client", forbidden)
        assert browser(local).get(path(foreign)).status_code == 404
        assert browser(local).get(f"/api/v1/projects/{uuid4()}/services/map/").status_code == 404
        assert APIClient().get(path(project)).status_code in {401, 403}

    def test_observed_pairs_only_and_deduplication(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = member("map-pairs")
        trace = "a" * 32
        other = "b" * 32
        root, child, orphan = "1" * 16, "2" * 16, "3" * 16
        rows = [
            span(trace, root, "0" * 16, "gateway", "prod"),
            span(trace, child, root, "checkout", "prod"),
            span(trace, child, root, "checkout", "prod"),  # exporter retry
            span(trace, orphan, "9" * 16, "unknown", "prod"),
            span(other, "4" * 16, root, "billing", "prod"),  # foreign trace, no parent
            span(trace, "5" * 16, child, "checkout", "prod"),  # same-service pair
        ]
        fake = FakeClient(rows)
        monkeypatch.setattr(service_map, "get_clickhouse_client", lambda: fake)
        response = browser(user).get(
            path(project),
            {"start": "2026-10-24T01:00:00Z", "end": "2026-10-24T03:00:00Z"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["relationships"] == [
            {
                "from_service": "gateway",
                "from_environment": "prod",
                "to_service": "checkout",
                "to_environment": "prod",
                "span_pairs": 1,
                "trace_ids": [trace],
            }
        ]
        assert body["scanned_spans"] == len(rows)
        assert body["truncated"] is False and body["span_scan_truncated"] is False
        assert fake.closed
        sql, args = fake.calls[0]
        assert "organization_id = {organization_id:UUID}" in sql
        assert "project_id = {project_id:UUID}" in sql
        assert "LIMIT 10001" in sql
        assert "max_rows_to_read = 250000" in sql
        assert args["organization_id"] == project.organization_id
        assert args["project_id"] == project.id

    def test_ambiguous_parent_and_child_are_not_edges(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("map-ambiguous")
        trace = "c" * 32
        rows = [
            span(trace, "1" * 16, "0" * 16, "gateway"),
            span(trace, "1" * 16, "0" * 16, "other-gateway"),
            span(trace, "2" * 16, "1" * 16, "checkout"),
            span(trace, "3" * 16, "2" * 16, "payments"),
            span(trace, "3" * 16, "2" * 16, "different-payments"),
        ]
        fake = FakeClient(rows)
        monkeypatch.setattr(service_map, "get_clickhouse_client", lambda: fake)
        response = browser(user).get(path(project))
        assert response.status_code == 200
        assert response.json()["relationships"] == []

    def test_edge_limit_and_scan_cap_cannot_appear_complete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("map-limits")
        trace = "d" * 32
        roots = [span(trace, f"{i:016x}", "0" * 16, f"root-{i}") for i in range(1, 4)]
        children = [span(trace, f"{i + 3:016x}", f"{i:016x}", f"leaf-{i}") for i in range(1, 4)]
        fake = FakeClient(roots + children)
        monkeypatch.setattr(service_map, "get_clickhouse_client", lambda: fake)
        response = browser(user).get(path(project), {"limit": 1})
        assert response.status_code == 200
        assert len(response.json()["relationships"]) == 1
        assert response.json()["truncated"] is True
        assert response.json()["span_scan_truncated"] is False

        fake.rows = [span("e" * 32, f"{i + 1:016x}", "0" * 16, "root") for i in range(10001)]
        response = browser(user).get(path(project))
        assert response.status_code == 200
        assert response.json()["relationships"] == []
        assert response.json()["truncated"] is True
        assert response.json()["span_scan_truncated"] is True
        assert response.json()["scanned_spans"] == 10000

    @pytest.mark.parametrize(
        "params",
        [
            {"limit": "0"},
            {"limit": "501"},
            {"limit": "bad"},
            {"start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:00Z"},
            {"start": "2026-10-24T12:00:00Z", "end": "2026-10-24T12:00:00Z"},
            {"start": "2026-10-24T12:00:00"},
        ],
    )
    def test_invalid_bounds(self, params: dict[str, str]) -> None:
        user, project = member("map-bounds")
        assert browser(user).get(path(project), params).status_code == 400

    def test_empty_default_window_and_dependency_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = member("map-empty")
        fake = FakeClient([])
        monkeypatch.setattr(service_map, "get_clickhouse_client", lambda: fake)
        body = browser(user).get(path(project)).json()
        assert body["relationships"] == []
        assert body["truncated"] is False
        start = datetime.fromisoformat(body["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(body["end"].replace("Z", "+00:00"))
        assert end - start == timedelta(days=1)
        fake.fail = True
        response = browser(user).get(path(project))
        assert response.status_code == 503
        assert "credentials" not in str(response.json())
        assert fake.closed


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_real_otlp_cross_service_pair_and_isolation() -> None:
    schema = get_clickhouse_client()
    try:
        ensure_clickhouse_schema(schema)
    finally:
        schema.close()
    owner, project = member("map-otlp")
    foreign, foreign_project = member("map-foreign-otlp")
    _, token = create_project_api_key(project=project, name="map exporter", created_by=owner)
    _, foreign_token = create_project_api_key(
        project=foreign_project, name="map foreign", created_by=foreign
    )
    trace_id = uuid4().bytes
    root_id = uuid4().bytes[:8]
    child_id = uuid4().bytes[:8]
    now = time.time_ns()
    payload = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value="m64-gateway"))
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=trace_id,
                                span_id=root_id,
                                name="request",
                                start_time_unix_nano=now,
                                end_time_unix_nano=now + 1_000_000,
                            )
                        ]
                    )
                ],
            ),
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value="m64-checkout"))
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=trace_id,
                                span_id=child_id,
                                parent_span_id=root_id,
                                name="charge",
                                start_time_unix_nano=now + 100,
                                end_time_unix_nano=now + 900_000,
                            )
                        ]
                    )
                ],
            ),
        ]
    ).SerializeToString()
    for secret in (token, foreign_token):
        response = APIClient().post(
            "/v1/traces",
            data=payload,
            content_type=OTLP_PROTOBUF_CONTENT_TYPE,
            HTTP_AUTHORIZATION=f"Bearer {secret}",
        )
        assert response.status_code == 200
    now_utc = datetime.now(UTC)
    params = {
        "start": (now_utc - timedelta(minutes=5)).isoformat(),
        "end": (now_utc + timedelta(minutes=5)).isoformat(),
    }
    data = browser(owner).get(path(project), params)
    assert data.status_code == 200
    matching = [
        edge
        for edge in data.json()["relationships"]
        if edge["from_service"] == "m64-gateway" and edge["to_service"] == "m64-checkout"
    ]
    assert len(matching) == 1
    assert matching[0]["span_pairs"] == 1
    assert matching[0]["trace_ids"] == [trace_id.hex()]
    assert browser(owner).get(path(foreign_project), params).status_code == 404
