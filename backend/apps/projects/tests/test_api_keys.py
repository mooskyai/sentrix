from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectApiKey


@pytest.mark.django_db
class TestProjectApiKeys:
    def _project(self, *, username: str, role: str, slug: str) -> tuple[User, Project]:
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

    @pytest.mark.parametrize(
        "role",
        [
            OrganizationMembership.Role.OWNER,
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.EDITOR,
        ],
    )
    def test_write_roles_can_create_project_api_key(self, role: str) -> None:
        user, project = self._project(username=f"user-{role}", role=role, slug=f"org-{role}")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {"name": "Collector"},
            format="json",
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["name"] == "Collector"
        assert payload["project_id"] == str(project.id)
        assert payload["scopes"] == ["telemetry:write"]
        assert payload["secret"].startswith(f"sentrix_pk_{payload['prefix']}_")

    def test_secret_is_returned_once_and_never_stored_in_plaintext(self) -> None:
        user, project = self._project(
            username="owner-secret",
            role=OrganizationMembership.Role.OWNER,
            slug="secret-org",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        create_response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {"name": "Production collector"},
            format="json",
        )
        payload = create_response.json()
        token = payload["secret"]
        api_key = ProjectApiKey.objects.get(pk=payload["id"])
        secret = token.split("_", 3)[3]

        assert api_key.secret_hash != token
        assert api_key.secret_hash != secret
        assert check_password(secret, api_key.secret_hash)

        list_response = client.get(f"/api/v1/projects/{project.id}/api-keys/")
        listed_key = list_response.json()[0]
        assert "secret" not in listed_key
        assert "secret_hash" not in listed_key

    def test_viewer_cannot_manage_project_api_keys(self) -> None:
        viewer, project = self._project(
            username="viewer-keys",
            role=OrganizationMembership.Role.VIEWER,
            slug="viewer-keys-org",
        )
        api_key = ProjectApiKey.objects.create(
            project=project,
            name="Existing",
            prefix="abc123def456",
            secret_hash="not-a-real-secret",
            scopes=["telemetry:write"],
        )
        client = APIClient()
        client.force_authenticate(user=viewer)

        list_response = client.get(f"/api/v1/projects/{project.id}/api-keys/")
        create_response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {"name": "Nope"},
            format="json",
        )
        revoke_response = client.delete(f"/api/v1/projects/{project.id}/api-keys/{api_key.id}/")

        assert list_response.status_code == 403
        assert create_response.status_code == 403
        assert revoke_response.status_code == 403

    def test_foreign_project_api_key_management_returns_not_found(self) -> None:
        owner_a, _ = self._project(
            username="key-owner-a",
            role=OrganizationMembership.Role.OWNER,
            slug="key-org-a",
        )
        _, project_b = self._project(
            username="key-owner-b",
            role=OrganizationMembership.Role.OWNER,
            slug="key-org-b",
        )
        client = APIClient()
        client.force_authenticate(user=owner_a)

        response = client.post(
            f"/api/v1/projects/{project_b.id}/api-keys/",
            {"name": "Cross tenant"},
            format="json",
        )

        assert response.status_code == 404
        assert ProjectApiKey.objects.count() == 0

    def test_revoke_keeps_key_metadata_and_marks_it_revoked(self) -> None:
        user, project = self._project(
            username="owner-revoke",
            role=OrganizationMembership.Role.OWNER,
            slug="revoke-org",
        )
        client = APIClient()
        client.force_authenticate(user=user)
        create_response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {"name": "Revoke me"},
            format="json",
        )
        api_key_id = create_response.json()["id"]

        revoke_response = client.delete(f"/api/v1/projects/{project.id}/api-keys/{api_key_id}/")
        list_response = client.get(f"/api/v1/projects/{project.id}/api-keys/")

        assert revoke_response.status_code == 204
        assert ProjectApiKey.objects.filter(pk=api_key_id).exists()
        assert list_response.json()[0]["revoked_at"] is not None

    def test_expiry_must_be_in_the_future(self) -> None:
        user, project = self._project(
            username="owner-expiry",
            role=OrganizationMembership.Role.OWNER,
            slug="expiry-org",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        expired_response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {
                "name": "Expired",
                "expires_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
            },
            format="json",
        )
        valid_response = client.post(
            f"/api/v1/projects/{project.id}/api-keys/",
            {
                "name": "Future",
                "expires_at": (timezone.now() + timedelta(days=30)).isoformat(),
            },
            format="json",
        )

        assert expired_response.status_code == 400
        assert valid_response.status_code == 201
