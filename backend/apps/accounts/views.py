from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import permissions, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, UserSerializer


def _authenticated_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticated("Authentication is required.")
    return user


class CsrfView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not isinstance(user, User):
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid credentials."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(_authenticated_user(request)).data)
