from django.contrib.auth.models import User
from django.db.models import QuerySet
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import BaseSerializer

from .models import Organization, OrganizationMembership
from .selectors import ADMIN_ROLES, organizations_for_user
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet[Organization]):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def _authenticated_user(self) -> User:
        user = self.request.user
        if not isinstance(user, User):
            raise PermissionDenied("Authentication is required.")
        return user

    def get_queryset(self) -> QuerySet[Organization]:
        return organizations_for_user(self._authenticated_user()).prefetch_related("memberships")

    def perform_update(self, serializer: BaseSerializer[Organization]) -> None:
        organization = self.get_object()
        role = (
            OrganizationMembership.objects.filter(
                organization=organization,
                user=self._authenticated_user(),
            )
            .values_list("role", flat=True)
            .first()
        )
        if role not in ADMIN_ROLES:
            raise PermissionDenied("Only organization owners and admins can update organizations.")
        serializer.save()
