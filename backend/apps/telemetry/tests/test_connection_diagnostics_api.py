"""M7.1 observation diagnostics must never infer health or bypass tenant scope."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.telemetry import connection_diagnostics


class Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, values: list[tuple[int, datetime | None]], *, fail_at: int = -1) -> None:
        self.values = values
        self.fail_at = fail_at
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def query(self, sql: str, *, parameters: dict[str, Any]) -> Result:
        self.calls.append((sql, parameters))
        if len(self.calls) == self.fail_at:
            raise RuntimeError("secret connection string")
        count, latest = self.values[len(self.calls) - 1]
        return Result([(count, latest)])

    def close(self) -> None:
        self.closed = True


def create_project(username: str) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User.objects.create_user(username=f"{username}-{suffix}")
    organization = Organization.objects.create(name="Example org", slug=f"org-{suffix}")
    OrganizationMembership.objects.create(
        user=user, organization=organization, role=OrganizationMembership.Role.VIEWER
    )
    project = Project.objects.create(
        organization=organization, name="Example project", slug="project", created_by=user
    )
    return user, project


def request_as(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestConnectionDiagnostics:
    def test_viewer_sees_exact_signal_observations_and_typed_tenant_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = create_project("first-telemetry")
        at = datetime.now(UTC) - timedelta(minutes=3)
        ch = FakeClient([(3, at), (1, at), (0, None)])
        monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", lambda: ch)
        response = request_as(user).get(
            f"/api/v1/projects/{project.id}/integrations/connection-status/"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["project_id"] == str(project.id)
        assert body["observation_state"] == "observed"
        assert body["signals"]["metrics"] == {
            "observed": True,
            "count": 3,
            "last_seen": at.isoformat().replace("+00:00", "Z"),
        }
        assert body["signals"]["logs"]["count"] == 1
        assert body["signals"]["traces"] == {"observed": False, "count": 0, "last_seen": None}
        start = datetime.fromisoformat(body["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(body["end"].replace("Z", "+00:00"))
        assert end - start == timedelta(hours=24)
        assert len(ch.calls) == 3
        for sql, params in ch.calls:
            assert "organization_id = {organization_id:UUID}" in sql
            assert "project_id = {project_id:UUID}" in sql
            assert "{start:DateTime64(9)}" in sql
            assert "{end:DateTime64(9)}" in sql
            assert "max_rows_to_read = 250000" in sql
            assert "read_overflow_mode = 'throw'" in sql
            assert params["organization_id"] == project.organization_id
            assert params["project_id"] == project.id
            assert params["start"] == start
            assert params["end"] == end
        assert ch.closed
        assert "key" not in str(body).lower()

    def test_healthy_empty_window_does_not_claim_connection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, project = create_project("empty-diag")
        ch = FakeClient([(0, None)] * 3)
        monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", lambda: ch)
        response = request_as(user).get(
            f"/api/v1/projects/{project.id}/integrations/connection-status/"
        )
        assert response.status_code == 200
        assert response.json()["observation_state"] == "not_observed"
        assert all(not item["observed"] for item in response.json()["signals"].values())
        assert ch.closed

    def test_foreign_and_missing_project_never_open_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user, _ = create_project("local-diag")
        _, foreign = create_project("foreign-diag")

        def forbidden() -> None:
            raise AssertionError("ClickHouse must never open for unauthorized project")

        monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", forbidden)
        client = request_as(user)
        assert (
            client.get(f"/api/v1/projects/{foreign.id}/integrations/connection-status/").status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/projects/{uuid4()}/integrations/connection-status/").status_code
            == 404
        )

    def test_anonymous_denied(self) -> None:
        _, project = create_project("anonymous-diag")
        client = APIClient()
        url = f"/api/v1/projects/{project.id}/integrations/connection-status/"
        assert client.get(url).status_code in {401, 403}
        assert client.get(url, HTTP_AUTHORIZATION="Bearer invalid").status_code in {401, 403}

    @pytest.mark.parametrize("fail_at", [1, 2, 3])
    def test_dependency_failure_is_503_not_empty_and_client_is_closed(
        self, monkeypatch: pytest.MonkeyPatch, fail_at: int
    ) -> None:
        user, project = create_project("unavailable-diag")
        ch = FakeClient([(1, datetime.now(UTC))] * 3, fail_at=fail_at)
        monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", lambda: ch)
        response = request_as(user).get(
            f"/api/v1/projects/{project.id}/integrations/connection-status/"
        )
        assert response.status_code == 503
        assert "secret connection string" not in str(response.json())
        assert ch.closed

    def test_invalid_result_is_not_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user, project = create_project("invalid-diag")
        ch = FakeClient([(1, None), (0, None), (0, None)])
        monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", lambda: ch)
        response = request_as(user).get(
            f"/api/v1/projects/{project.id}/integrations/connection-status/"
        )
        assert response.status_code == 503
        assert ch.closed


def test_rejects_invalid_window_without_query(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden() -> None:
        raise AssertionError("unexpected query")

    monkeypatch.setattr(connection_diagnostics, "get_clickhouse_client", forbidden)
    at = datetime.now(UTC)
    with pytest.raises(ValueError):
        connection_diagnostics.recent_signal_observations(
            organization_id=uuid4(), project_id=uuid4(), start=at, end=at
        )
