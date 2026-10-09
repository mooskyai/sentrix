import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectDashboardPanel


@pytest.mark.django_db
class TestProjectDashboardPanels:
    def _project(self, username: str, slug: str, role: str) -> tuple[User, Project]:
        user = User.objects.create_user(username=username)
        organization = Organization.objects.create(name=slug.upper(), slug=slug)
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=role,
        )
        project = Project.objects.create(
            organization=organization,
            name=f"{slug} project",
            slug="app",
            created_by=user,
        )
        return user, project

    def _client(self, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_viewer_can_list_project_dashboard_panels(self) -> None:
        owner, project = self._project(
            "panel-owner",
            "panel-org",
            OrganizationMembership.Role.OWNER,
        )
        viewer = User.objects.create_user(username="panel-viewer")
        OrganizationMembership.objects.create(
            organization=project.organization,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )
        ProjectDashboardPanel.objects.create(
            project=project,
            title="Request volume",
            metric_name="http.server.requests",
            time_range="1h",
            created_by=owner,
        )

        response = self._client(viewer).get(f"/api/v1/projects/{project.id}/dashboard-panels/")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["metric_name"] == "http.server.requests"
        assert payload[0]["project_id"] == str(project.id)

    def test_owner_can_pin_dashboard_panel(self) -> None:
        owner, project = self._project(
            "panel-create-owner",
            "panel-create-org",
            OrganizationMembership.Role.OWNER,
        )

        response = self._client(owner).post(
            f"/api/v1/projects/{project.id}/dashboard-panels/",
            {
                "title": "Checkout latency",
                "metric_name": "checkout.duration",
                "time_range": "6h",
                "service_name": "checkout",
                "environment": "production",
            },
            format="json",
        )

        assert response.status_code == 201
        panel = ProjectDashboardPanel.objects.get()
        assert panel.project == project
        assert panel.created_by == owner
        assert panel.position == 0
        assert panel.service_name == "checkout"
        assert response.json()["time_range"] == "6h"

    def test_viewer_cannot_pin_or_remove_dashboard_panel(self) -> None:
        owner, project = self._project(
            "panel-rbac-owner",
            "panel-rbac-org",
            OrganizationMembership.Role.OWNER,
        )
        viewer = User.objects.create_user(username="panel-rbac-viewer")
        OrganizationMembership.objects.create(
            organization=project.organization,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )
        panel = ProjectDashboardPanel.objects.create(
            project=project,
            title="Read only",
            metric_name="read.only.metric",
            created_by=owner,
        )
        client = self._client(viewer)

        create_response = client.post(
            f"/api/v1/projects/{project.id}/dashboard-panels/",
            {
                "title": "Denied",
                "metric_name": "denied.metric",
                "time_range": "1h",
            },
            format="json",
        )
        delete_response = client.delete(
            f"/api/v1/projects/{project.id}/dashboard-panels/{panel.id}/"
        )

        assert create_response.status_code == 403
        assert delete_response.status_code == 403
        assert ProjectDashboardPanel.objects.filter(pk=panel.pk).exists()

    def test_foreign_project_is_not_discoverable(self) -> None:
        user_a, _project_a = self._project(
            "panel-tenant-a",
            "panel-tenant-a-org",
            OrganizationMembership.Role.OWNER,
        )
        _user_b, project_b = self._project(
            "panel-tenant-b",
            "panel-tenant-b-org",
            OrganizationMembership.Role.OWNER,
        )

        response = self._client(user_a).get(f"/api/v1/projects/{project_b.id}/dashboard-panels/")

        assert response.status_code == 404

    def test_panel_delete_is_scoped_to_route_project(self) -> None:
        owner_a, project_a = self._project(
            "panel-delete-a",
            "panel-delete-a-org",
            OrganizationMembership.Role.OWNER,
        )
        owner_b, project_b = self._project(
            "panel-delete-b",
            "panel-delete-b-org",
            OrganizationMembership.Role.OWNER,
        )
        panel_b = ProjectDashboardPanel.objects.create(
            project=project_b,
            title="Foreign panel",
            metric_name="foreign.metric",
            created_by=owner_b,
        )

        response = self._client(owner_a).delete(
            f"/api/v1/projects/{project_a.id}/dashboard-panels/{panel_b.id}/"
        )

        assert response.status_code == 404
        assert ProjectDashboardPanel.objects.filter(pk=panel_b.pk).exists()

    def test_duplicate_panel_query_is_rejected(self) -> None:
        owner, project = self._project(
            "panel-duplicate",
            "panel-duplicate-org",
            OrganizationMembership.Role.OWNER,
        )
        client = self._client(owner)
        payload = {
            "title": "CPU",
            "metric_name": "process.cpu.utilization",
            "time_range": "1h",
            "service_name": "api",
            "environment": "production",
        }

        first = client.post(
            f"/api/v1/projects/{project.id}/dashboard-panels/",
            payload,
            format="json",
        )
        second = client.post(
            f"/api/v1/projects/{project.id}/dashboard-panels/",
            {**payload, "title": "Same query, different title"},
            format="json",
        )

        assert first.status_code == 201
        assert second.status_code == 400
        assert ProjectDashboardPanel.objects.count() == 1

    def test_dashboard_panel_count_is_bounded(self) -> None:
        owner, project = self._project(
            "panel-limit",
            "panel-limit-org",
            OrganizationMembership.Role.OWNER,
        )
        client = self._client(owner)

        for index in range(6):
            response = client.post(
                f"/api/v1/projects/{project.id}/dashboard-panels/",
                {
                    "title": f"Metric {index}",
                    "metric_name": f"metric.{index}",
                    "time_range": "1h",
                },
                format="json",
            )
            assert response.status_code == 201

        overflow = client.post(
            f"/api/v1/projects/{project.id}/dashboard-panels/",
            {
                "title": "Metric 7",
                "metric_name": "metric.7",
                "time_range": "1h",
            },
            format="json",
        )

        assert overflow.status_code == 400
        assert ProjectDashboardPanel.objects.count() == 6
