import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.alerts.models import AlertRule
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project


@pytest.mark.django_db
class TestAlertRuleApi:
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

    def _rule(
        self,
        *,
        project: Project,
        created_by: User,
        name: str = "High latency",
    ) -> AlertRule:
        return AlertRule.objects.create(
            project=project,
            name=name,
            metric_name="http.server.duration",
            time_range=AlertRule.TimeRange.ONE_HOUR,
            service_name="api",
            environment="production",
            comparator=AlertRule.Comparator.GREATER_THAN,
            threshold=250.0,
            created_by=created_by,
        )

    def test_viewer_can_list_project_alert_rules(self) -> None:
        owner, project = self._project(
            "alert-owner",
            "alert-org",
            OrganizationMembership.Role.OWNER,
        )
        viewer = User.objects.create_user(username="alert-viewer")
        OrganizationMembership.objects.create(
            organization=project.organization,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )
        rule = self._rule(project=project, created_by=owner)

        response = self._client(viewer).get(f"/api/v1/projects/{project.id}/alert-rules/")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == str(rule.id)
        assert payload[0]["project_id"] == str(project.id)
        assert payload[0]["threshold"] == 250.0

    def test_owner_can_create_typed_metric_rule(self) -> None:
        owner, project = self._project(
            "alert-create-owner",
            "alert-create-org",
            OrganizationMembership.Role.OWNER,
        )

        response = self._client(owner).post(
            f"/api/v1/projects/{project.id}/alert-rules/",
            {
                "name": "Checkout latency",
                "metric_name": "checkout.duration",
                "time_range": "6h",
                "service_name": "checkout",
                "environment": "production",
                "comparator": "gte",
                "threshold": 500.5,
                "enabled": True,
            },
            format="json",
        )

        assert response.status_code == 201
        rule = AlertRule.objects.get()
        assert rule.project == project
        assert rule.created_by == owner
        assert rule.metric_name == "checkout.duration"
        assert rule.time_range == "6h"
        assert rule.comparator == "gte"
        assert rule.threshold == 500.5
        assert response.json()["enabled"] is True

    def test_viewer_cannot_create_update_or_delete_rules(self) -> None:
        owner, project = self._project(
            "alert-rbac-owner",
            "alert-rbac-org",
            OrganizationMembership.Role.OWNER,
        )
        viewer = User.objects.create_user(username="alert-rbac-viewer")
        OrganizationMembership.objects.create(
            organization=project.organization,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )
        rule = self._rule(project=project, created_by=owner)
        client = self._client(viewer)

        create_response = client.post(
            f"/api/v1/projects/{project.id}/alert-rules/",
            {
                "name": "Denied",
                "metric_name": "denied.metric",
                "comparator": "gt",
                "threshold": 1,
            },
            format="json",
        )
        patch_response = client.patch(
            f"/api/v1/projects/{project.id}/alert-rules/{rule.id}/",
            {"enabled": False},
            format="json",
        )
        delete_response = client.delete(f"/api/v1/projects/{project.id}/alert-rules/{rule.id}/")

        assert create_response.status_code == 403
        assert patch_response.status_code == 403
        assert delete_response.status_code == 403
        rule.refresh_from_db()
        assert rule.enabled is True

    def test_foreign_project_is_not_discoverable(self) -> None:
        user_a, _project_a = self._project(
            "alert-tenant-a",
            "alert-tenant-a-org",
            OrganizationMembership.Role.OWNER,
        )
        _user_b, project_b = self._project(
            "alert-tenant-b",
            "alert-tenant-b-org",
            OrganizationMembership.Role.OWNER,
        )

        response = self._client(user_a).get(f"/api/v1/projects/{project_b.id}/alert-rules/")

        assert response.status_code == 404

    def test_alert_rule_detail_is_scoped_to_route_project(self) -> None:
        owner_a, project_a = self._project(
            "alert-detail-a",
            "alert-detail-a-org",
            OrganizationMembership.Role.OWNER,
        )
        owner_b, project_b = self._project(
            "alert-detail-b",
            "alert-detail-b-org",
            OrganizationMembership.Role.OWNER,
        )
        rule_b = self._rule(project=project_b, created_by=owner_b, name="Foreign rule")

        response = self._client(owner_a).delete(
            f"/api/v1/projects/{project_a.id}/alert-rules/{rule_b.id}/"
        )

        assert response.status_code == 404
        assert AlertRule.objects.filter(pk=rule_b.pk).exists()

    def test_rule_patch_preserves_unspecified_condition_fields(self) -> None:
        owner, project = self._project(
            "alert-patch-owner",
            "alert-patch-org",
            OrganizationMembership.Role.OWNER,
        )
        rule = self._rule(project=project, created_by=owner)

        response = self._client(owner).patch(
            f"/api/v1/projects/{project.id}/alert-rules/{rule.id}/",
            {"threshold": 300, "enabled": False},
            format="json",
        )

        assert response.status_code == 200
        rule.refresh_from_db()
        assert rule.threshold == 300.0
        assert rule.enabled is False
        assert rule.metric_name == "http.server.duration"
        assert rule.service_name == "api"
        assert rule.environment == "production"

    def test_duplicate_rule_name_is_rejected_within_project(self) -> None:
        owner, project = self._project(
            "alert-duplicate-owner",
            "alert-duplicate-org",
            OrganizationMembership.Role.OWNER,
        )
        self._rule(project=project, created_by=owner, name="Duplicate")

        response = self._client(owner).post(
            f"/api/v1/projects/{project.id}/alert-rules/",
            {
                "name": "Duplicate",
                "metric_name": "another.metric",
                "comparator": "lt",
                "threshold": 10,
            },
            format="json",
        )

        assert response.status_code == 400
        assert AlertRule.objects.filter(project=project).count() == 1

    @pytest.mark.parametrize("threshold", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_threshold_is_rejected(self, threshold: str) -> None:
        suffix = threshold.lower().replace("-", "neg")
        owner, project = self._project(
            f"alert-finite-{suffix}",
            f"alert-finite-{suffix}-org",
            OrganizationMembership.Role.OWNER,
        )

        response = self._client(owner).post(
            f"/api/v1/projects/{project.id}/alert-rules/",
            {
                "name": "Finite only",
                "metric_name": "finite.metric",
                "comparator": "gt",
                "threshold": threshold,
            },
            format="json",
        )

        assert response.status_code == 400
        assert AlertRule.objects.filter(project=project).count() == 0

    def test_alert_rule_count_is_bounded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        owner, project = self._project(
            "alert-limit-owner",
            "alert-limit-org",
            OrganizationMembership.Role.OWNER,
        )
        monkeypatch.setattr("apps.alerts.services.MAX_PROJECT_ALERT_RULES", 1)
        self._rule(project=project, created_by=owner, name="Existing")

        response = self._client(owner).post(
            f"/api/v1/projects/{project.id}/alert-rules/",
            {
                "name": "Overflow",
                "metric_name": "overflow.metric",
                "comparator": "gt",
                "threshold": 1,
            },
            format="json",
        )

        assert response.status_code == 400
        assert AlertRule.objects.filter(project=project).count() == 1
