from datetime import datetime
from typing import Any

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.selectors import WRITE_ROLES

from .models import Project, ProjectApiKey


class ProjectSerializer(serializers.ModelSerializer[Project]):
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.all(),
    )

    class Meta:
        model = Project
        fields = (
            "id",
            "organization_id",
            "name",
            "slug",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate_organization_id(self, organization: Organization) -> Organization:
        request = self.context["request"]
        user = request.user
        if not isinstance(user, User):
            raise serializers.ValidationError("Authentication is required.")

        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=user,
        ).first()
        if membership is None:
            raise serializers.ValidationError("You do not have access to this organization.")
        if self.instance is None and membership.role not in WRITE_ROLES:
            raise serializers.ValidationError("Your role cannot create projects.")
        return organization

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance
        if (
            isinstance(instance, Project)
            and "organization" in attrs
            and attrs["organization"].pk != instance.organization_id
        ):
            raise serializers.ValidationError(
                {"organization_id": "Moving a project between organizations is not supported."}
            )
        return attrs


class ProjectApiKeySerializer(serializers.ModelSerializer[ProjectApiKey]):
    project_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ProjectApiKey
        fields = (
            "id",
            "project_id",
            "name",
            "prefix",
            "scopes",
            "created_by",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "created_at",
        )
        read_only_fields = fields


class ProjectApiKeyCreateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=160)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value: datetime | None) -> datetime | None:
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiry must be in the future.")
        return value
