from uuid import UUID

from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.organizations.models import OrganizationMembership
from apps.organizations.selectors import WRITE_ROLES, membership_for_user

from .models import Project, ProjectApiKey
from .selectors import projects_for_user
from .serializers import (
    ProjectApiKeyCreateSerializer,
    ProjectApiKeySerializer,
    ProjectSerializer,
)
from .services import create_project_api_key


def _authenticated_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User):
        raise PermissionDenied("Authentication is required.")
    return user


def _managed_project(request: Request, project_id: UUID) -> Project:
    user = _authenticated_user(request)
    try:
        project = projects_for_user(user).select_related("organization").get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise NotFound("Project not found.") from exc

    membership = membership_for_user(user=user, organization=project.organization)
    if membership is None or membership.role not in WRITE_ROLES:
        raise PermissionDenied("Your role cannot manage project API keys.")
    return project


class ProjectViewSet(viewsets.ModelViewSet[Project]):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _authenticated_user(self) -> User:
        return _authenticated_user(self.request)

    def get_queryset(self) -> QuerySet[Project]:
        return projects_for_user(self._authenticated_user()).select_related(
            "organization", "created_by"
        )

    def perform_create(self, serializer: BaseSerializer[Project]) -> None:
        serializer.save(created_by=self._authenticated_user())

    def _require_write_role(self, project: Project) -> None:
        role = (
            OrganizationMembership.objects.filter(
                organization=project.organization,
                user=self._authenticated_user(),
            )
            .values_list("role", flat=True)
            .first()
        )
        if role not in WRITE_ROLES:
            raise PermissionDenied("Your role cannot modify this project.")

    def perform_update(self, serializer: BaseSerializer[Project]) -> None:
        project = self.get_object()
        self._require_write_role(project)
        serializer.save()

    def perform_destroy(self, instance: Project) -> None:
        self._require_write_role(instance)
        instance.delete()


class ProjectApiKeyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _managed_project(request, project_id)
        api_keys = ProjectApiKey.objects.filter(project=project).select_related("created_by")
        return Response(ProjectApiKeySerializer(api_keys, many=True).data)

    def post(self, request: Request, project_id: UUID) -> Response:
        project = _managed_project(request, project_id)
        serializer = ProjectApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key, secret = create_project_api_key(
            project=project,
            name=serializer.validated_data["name"],
            created_by=_authenticated_user(request),
            expires_at=serializer.validated_data.get("expires_at"),
        )
        payload = dict(ProjectApiKeySerializer(api_key).data)
        payload["secret"] = secret
        return Response(payload, status=status.HTTP_201_CREATED)


class ProjectApiKeyRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request: Request, project_id: UUID, api_key_id: UUID) -> Response:
        project = _managed_project(request, project_id)
        try:
            api_key = ProjectApiKey.objects.get(pk=api_key_id, project=project)
        except ProjectApiKey.DoesNotExist as exc:
            raise NotFound("API key not found.") from exc

        if api_key.revoked_at is None:
            api_key.revoked_at = timezone.now()
            api_key.save(update_fields=["revoked_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
