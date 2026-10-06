import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAuthApi:
    def test_authenticated_user_can_read_me(self) -> None:
        user = User.objects.create_user(username="udit", email="udit@example.test")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/v1/auth/me/")

        assert response.status_code == 200
        assert response.json()["username"] == "udit"

    def test_anonymous_user_cannot_read_me(self) -> None:
        response = APIClient().get("/api/v1/auth/me/")
        assert response.status_code in {401, 403}
