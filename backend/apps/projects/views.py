from uuid import UUID

from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.organizations.models import OrganizationMembership
from apps.organizations.selectors import WRITE_ROLES, membership_for_user

from .models import Project, ProjectApiKey, ProjectDashboardPanel
from .selectors import projects_for_user
from .serializers import (
    ProjectApiKeyCreateSerializer,
    ProjectApiKeySerializer,
    ProjectDashboardPanelCreateSerializer,
    ProjectDashboardPanelSerializer,
    ProjectSerializer,
)
from .services import (
    DashboardPanelAlreadyExists,
    DashboardPanelLimitReached,
    create_project_api_key,
    create_project_dashboard_panel,
)


def _authenticated_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User):
        raise PermissionDenied("Authentication is required.")
    return user


def _readable_project(request: Request, project_id: UUID) -> Project:
    user = _authenticated_user(request)
    try:
        return projects_for_user(user).select_related("organization").get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise NotFound("Project not found.") from exc


def _writable_project(request: Request, project_id: UUID, detail: str) -> Project:
    project = _readable_project(request, project_id)
    membership = membership_for_user(
        user=_authenticated_user(request),
        organization=project.organization,
    )
    if membership is None or membership.role not in WRITE_ROLES:
        raise PermissionDenied(detail)
    return project


def _managed_project(request: Request, project_id: UUID) -> Project:
    return _writable_project(
        request,
        project_id,
        "Your role cannot manage project API keys.",
    )


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


class ProjectDashboardPanelListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        panels = ProjectDashboardPanel.objects.filter(project=project).select_related("created_by")
        return Response(ProjectDashboardPanelSerializer(panels, many=True).data)

    def post(self, request: Request, project_id: UUID) -> Response:
        project = _writable_project(
            request,
            project_id,
            "Your role cannot manage dashboard panels.",
        )
        serializer = ProjectDashboardPanelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            panel = create_project_dashboard_panel(
                project=project,
                title=serializer.validated_data["title"],
                metric_name=serializer.validated_data["metric_name"],
                time_range=serializer.validated_data["time_range"],
                service_name=serializer.validated_data["service_name"],
                environment=serializer.validated_data["environment"],
                created_by=_authenticated_user(request),
            )
        except (DashboardPanelAlreadyExists, DashboardPanelLimitReached) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ProjectDashboardPanelSerializer(panel).data, status=status.HTTP_201_CREATED)


class ProjectDashboardPanelDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request: Request, project_id: UUID, panel_id: UUID) -> Response:
        project = _writable_project(
            request,
            project_id,
            "Your role cannot manage dashboard panels.",
        )
        try:
            panel = ProjectDashboardPanel.objects.get(pk=panel_id, project=project)
        except ProjectDashboardPanel.DoesNotExist as exc:
            raise NotFound("Dashboard panel not found.") from exc
        panel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
