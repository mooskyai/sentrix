from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from .models import Organization, OrganizationMembership


class OrganizationSerializer(serializers.ModelSerializer[Organization]):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "role", "created_at", "updated_at")
        read_only_fields = ("id", "role", "created_at", "updated_at")

    def get_role(self, obj: Organization) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not isinstance(user, User):
            return None
        membership = obj.memberships.filter(user=user).only("role").first()
        return membership.role if membership else None

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> Organization:
        request = self.context["request"]
        user = request.user
        if not isinstance(user, User):
            raise serializers.ValidationError("Authentication is required.")

        organization = Organization.objects.create(**validated_data)
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.Role.OWNER,
        )
        return organization
