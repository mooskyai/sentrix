from typing import Any

from django.contrib.auth.models import User
from rest_framework import serializers


class LoginSerializer(serializers.Serializer[Any]):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = fields
