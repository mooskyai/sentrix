import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.organizations.models import OrganizationMembership


@pytest.mark.django_db
class TestOrganizationsApi:
    def test_create_organization_creates_owner_membership(self) -> None:
        user = User.objects.create_user(username="owner", password="test-pass-123")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/organizations/",
            {"name": "Acme", "slug": "acme"},
            format="json",
        )

        assert response.status_code == 201
        membership = OrganizationMembership.objects.get(user=user)
        assert membership.role == OrganizationMembership.Role.OWNER

    def test_user_cannot_list_foreign_organization(self) -> None:
        user_a = User.objects.create_user(username="a")
        user_b = User.objects.create_user(username="b")
        client_b = APIClient()
        client_b.force_authenticate(user=user_b)
        created = client_b.post(
            "/api/v1/organizations/", {"name": "B", "slug": "b"}, format="json"
        )
        assert created.status_code == 201

        client_a = APIClient()
        client_a.force_authenticate(user=user_a)
        response = client_a.get("/api/v1/organizations/")

        assert response.status_code == 200
        assert response.json() == []
