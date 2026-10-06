from django.contrib.auth.models import User
from django.db.models import QuerySet
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import BaseSerializer

from apps.organizations.models import OrganizationMembership
from apps.organizations.selectors import WRITE_ROLES

from .models import Project
from .selectors import projects_for_user
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet[Project]):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _authenticated_user(self) -> User:
        user = self.request.user
        if not isinstance(user, User):
            raise PermissionDenied("Authentication is required.")
        return user

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
