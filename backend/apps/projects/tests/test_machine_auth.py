from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import override_settings
from django.urls import path
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.authentication import (
    HasProjectApiKeyScopes,
    ProjectApiKeyAuthentication,
    ProjectApiKeyPrincipal,
)
from apps.projects.models import Project, ProjectApiKey
from apps.projects.services import TELEMETRY_WRITE_SCOPE, create_project_api_key


class MachineProbeView(APIView):
    authentication_classes = [ProjectApiKeyAuthentication]
    permission_classes = [HasProjectApiKeyScopes]
    required_machine_scopes = (TELEMETRY_WRITE_SCOPE,)

    def post(self, request: Request) -> Response:
        principal = request.user
        assert isinstance(principal, ProjectApiKeyPrincipal)
        return Response(
            {
                "api_key_id": str(principal.api_key_id),
                "project_id": str(principal.project_id),
                "organization_id": str(principal.organization_id),
                "scopes": sorted(principal.scopes),
            }
        )


urlpatterns = [path("machine-probe/", MachineProbeView.as_view())]


@pytest.mark.django_db
class TestProjectApiKeyAuthentication:
    def _project(self, username: str = "machine-owner") -> tuple[User, Project]:
        user = User.objects.create_user(username=username)
        organization = Organization.objects.create(
            name=f"{username} organization",
            slug=f"{username}-org",
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.Role.OWNER,
        )
        project = Project.objects.create(
            organization=organization,
            name="Application",
            slug="app",
            created_by=user,
        )
        return user, project

    def _request(self, authorization: str | None = None) -> HttpRequest:
        factory = APIRequestFactory()
        headers = {} if authorization is None else {"HTTP_AUTHORIZATION": authorization}
        return factory.post("/machine-probe/", {}, format="json", **headers)

    def test_valid_bearer_key_authenticates_project_context_and_updates_last_used(self) -> None:
        user, project = self._project()
        api_key, token = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
        )

        response = MachineProbeView.as_view()(self._request(f"Bearer {token}"))

        api_key.refresh_from_db()
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.data == {
            "api_key_id": str(api_key.id),
            "project_id": str(project.id),
            "organization_id": str(project.organization_id),
            "scopes": [TELEMETRY_WRITE_SCOPE],
        }
        assert api_key.last_used_at is not None

    def test_wrong_secret_is_rejected_without_updating_last_used(self) -> None:
        user, project = self._project("wrong-secret-owner")
        api_key, _ = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
        )
        token = f"sentrix_pk_{api_key.prefix}_definitely-wrong"

        response = MachineProbeView.as_view()(self._request(f"Bearer {token}"))

        api_key.refresh_from_db()
        assert response.status_code == 401
        assert api_key.last_used_at is None

    def test_revoked_key_is_rejected_without_updating_last_used(self) -> None:
        user, project = self._project("revoked-owner")
        api_key, token = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
        )
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at", "updated_at"])

        response = MachineProbeView.as_view()(self._request(f"Bearer {token}"))

        api_key.refresh_from_db()
        assert response.status_code == 401
        assert api_key.last_used_at is None

    def test_expired_key_is_rejected_without_updating_last_used(self) -> None:
        user, project = self._project("expired-owner")
        api_key, token = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = MachineProbeView.as_view()(self._request(f"Bearer {token}"))

        api_key.refresh_from_db()
        assert response.status_code == 401
        assert api_key.last_used_at is None

    def test_valid_key_without_required_scope_is_forbidden(self) -> None:
        user, project = self._project("scope-owner")
        api_key, token = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
        )
        api_key.scopes = []
        api_key.save(update_fields=["scopes", "updated_at"])

        response = MachineProbeView.as_view()(self._request(f"Bearer {token}"))

        api_key.refresh_from_db()
        assert response.status_code == 403
        assert api_key.last_used_at is not None

    @pytest.mark.parametrize(
        "authorization",
        [
            "Bearer not-a-sentrix-key",
            "Bearer sentrix_pk_deadbeefdead_unknown-secret",
        ],
    )
    def test_malformed_or_unknown_key_is_rejected(self, authorization: str) -> None:
        response = MachineProbeView.as_view()(self._request(authorization))

        assert response.status_code == 401

    @override_settings(ROOT_URLCONF=__name__)
    def test_browser_user_without_machine_bearer_key_is_rejected(self) -> None:
        user, _ = self._project("session-only-owner")
        client = APIClient()
        client.force_login(user)

        response = client.post("/machine-probe/", {}, format="json")

        assert response.status_code == 401

    def test_machine_authentication_returns_the_api_key_as_request_auth(self) -> None:
        user, project = self._project("request-auth-owner")
        api_key, token = create_project_api_key(
            project=project,
            name="Collector",
            created_by=user,
        )
        raw_request = self._request(f"Bearer {token}")
        request = Request(raw_request)
        result = ProjectApiKeyAuthentication().authenticate(request)

        assert result is not None
        principal, request_auth = result
        assert isinstance(principal, ProjectApiKeyPrincipal)
        assert isinstance(request_auth, ProjectApiKey)
        assert request_auth.pk == api_key.pk
