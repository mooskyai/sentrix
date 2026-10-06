import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project


@pytest.mark.django_db
class TestProjectsApi:
    def _org(self, user: User, slug: str, role: str) -> Organization:
        org = Organization.objects.create(name=slug.upper(), slug=slug)
        OrganizationMembership.objects.create(organization=org, user=user, role=role)
        return org

    def test_project_list_is_tenant_scoped(self) -> None:
        user_a = User.objects.create_user(username="a")
        user_b = User.objects.create_user(username="b")
        org_a = self._org(user_a, "org-a", OrganizationMembership.Role.OWNER)
        org_b = self._org(user_b, "org-b", OrganizationMembership.Role.OWNER)
        Project.objects.create(organization=org_a, name="A", slug="a", created_by=user_a)
        Project.objects.create(organization=org_b, name="B", slug="b", created_by=user_b)

        client = APIClient()
        client.force_authenticate(user=user_a)
        response = client.get("/api/v1/projects/")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["slug"] == "a"

    def test_foreign_project_uuid_is_not_accessible(self) -> None:
        user_a = User.objects.create_user(username="a")
        user_b = User.objects.create_user(username="b")
        self._org(user_a, "org-a", OrganizationMembership.Role.OWNER)
        org_b = self._org(user_b, "org-b", OrganizationMembership.Role.OWNER)
        foreign_project = Project.objects.create(
            organization=org_b, name="Private", slug="private", created_by=user_b
        )

        client = APIClient()
        client.force_authenticate(user=user_a)
        response = client.get(f"/api/v1/projects/{foreign_project.id}/")

        assert response.status_code == 404

    def test_viewer_cannot_create_project(self) -> None:
        viewer = User.objects.create_user(username="viewer")
        org = self._org(viewer, "org", OrganizationMembership.Role.VIEWER)
        client = APIClient()
        client.force_authenticate(user=viewer)

        response = client.post(
            "/api/v1/projects/",
            {"organization_id": str(org.id), "name": "Nope", "slug": "nope"},
            format="json",
        )

        assert response.status_code == 400
        assert Project.objects.count() == 0

    def test_non_member_cannot_create_project(self) -> None:
        owner = User.objects.create_user(username="owner")
        outsider = User.objects.create_user(username="outsider")
        org = self._org(owner, "private-org", OrganizationMembership.Role.OWNER)
        client = APIClient()
        client.force_authenticate(user=outsider)

        response = client.post(
            "/api/v1/projects/",
            {"organization_id": str(org.id), "name": "Nope", "slug": "nope"},
            format="json",
        )

        assert response.status_code == 400
        assert Project.objects.count() == 0

    def test_editor_can_create_project(self) -> None:
        editor = User.objects.create_user(username="editor")
        org = self._org(editor, "editor-org", OrganizationMembership.Role.EDITOR)
        client = APIClient()
        client.force_authenticate(user=editor)

        response = client.post(
            "/api/v1/projects/",
            {"organization_id": str(org.id), "name": "Allowed", "slug": "allowed"},
            format="json",
        )

        assert response.status_code == 201
        project = Project.objects.get()
        assert project.organization == org
        assert project.created_by == editor

    def test_viewer_cannot_update_or_delete_project(self) -> None:
        viewer = User.objects.create_user(username="viewer-update")
        org = self._org(viewer, "viewer-org", OrganizationMembership.Role.VIEWER)
        project = Project.objects.create(organization=org, name="Read only", slug="read-only")
        client = APIClient()
        client.force_authenticate(user=viewer)

        update_response = client.patch(
            f"/api/v1/projects/{project.id}/",
            {"name": "Changed"},
            format="json",
        )
        delete_response = client.delete(f"/api/v1/projects/{project.id}/")

        project.refresh_from_db()
        assert update_response.status_code == 403
        assert delete_response.status_code == 403
        assert project.name == "Read only"
        assert Project.objects.filter(pk=project.pk).exists()

    def test_editor_can_update_project(self) -> None:
        editor = User.objects.create_user(username="editor-update")
        org = self._org(editor, "editor-update-org", OrganizationMembership.Role.EDITOR)
        project = Project.objects.create(organization=org, name="Before", slug="before")
        client = APIClient()
        client.force_authenticate(user=editor)

        response = client.patch(
            f"/api/v1/projects/{project.id}/",
            {"name": "After"},
            format="json",
        )

        project.refresh_from_db()
        assert response.status_code == 200
        assert project.name == "After"

    def test_foreign_project_cannot_be_mutated_by_exact_uuid(self) -> None:
        user_a = User.objects.create_user(username="mutation-a")
        user_b = User.objects.create_user(username="mutation-b")
        self._org(user_a, "mutation-org-a", OrganizationMembership.Role.OWNER)
        org_b = self._org(user_b, "mutation-org-b", OrganizationMembership.Role.OWNER)
        foreign_project = Project.objects.create(
            organization=org_b,
            name="Foreign",
            slug="foreign",
            created_by=user_b,
        )
        client = APIClient()
        client.force_authenticate(user=user_a)

        update_response = client.patch(
            f"/api/v1/projects/{foreign_project.id}/",
            {"name": "Compromised"},
            format="json",
        )
        delete_response = client.delete(f"/api/v1/projects/{foreign_project.id}/")

        foreign_project.refresh_from_db()
        assert update_response.status_code == 404
        assert delete_response.status_code == 404
        assert foreign_project.name == "Foreign"
        assert Project.objects.filter(pk=foreign_project.pk).exists()
