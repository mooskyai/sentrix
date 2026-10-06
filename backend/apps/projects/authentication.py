from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import ProjectApiKey
from .services import API_KEY_TOKEN_PREFIX


@dataclass(frozen=True, slots=True)
class ProjectApiKeyPrincipal:
    api_key_id: UUID
    project_id: UUID
    organization_id: UUID
    scopes: frozenset[str]

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


def _invalid_api_key() -> AuthenticationFailed:
    return AuthenticationFailed("Invalid project API key.")


def _parse_project_api_key(token: str) -> tuple[str, str]:
    marker = f"{API_KEY_TOKEN_PREFIX}_"
    if not token.startswith(marker):
        raise _invalid_api_key()

    remainder = token[len(marker) :]
    public_prefix, separator, secret = remainder.partition("_")
    if (
        separator != "_"
        or len(public_prefix) != 12
        or not public_prefix.isascii()
        or any(character not in "0123456789abcdef" for character in public_prefix)
        or not secret
    ):
        raise _invalid_api_key()
    return public_prefix, secret


def _scopes_for_key(api_key: ProjectApiKey) -> frozenset[str]:
    raw_scopes = api_key.scopes
    if not isinstance(raw_scopes, list):
        return frozenset()
    return frozenset(scope for scope in raw_scopes if isinstance(scope, str))


def authenticate_project_api_key(
    token: str,
) -> tuple[ProjectApiKeyPrincipal, ProjectApiKey]:
    public_prefix, secret = _parse_project_api_key(token)

    try:
        api_key = ProjectApiKey.objects.select_related("project__organization").get(
            prefix=public_prefix
        )
    except ProjectApiKey.DoesNotExist as exc:
        raise _invalid_api_key() from exc

    if not check_password(secret, api_key.secret_hash):
        raise _invalid_api_key()

    now = timezone.now()
    if api_key.revoked_at is not None:
        raise _invalid_api_key()
    if api_key.expires_at is not None and api_key.expires_at <= now:
        raise _invalid_api_key()

    ProjectApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now)
    api_key.last_used_at = now
    principal = ProjectApiKeyPrincipal(
        api_key_id=api_key.id,
        project_id=api_key.project_id,
        organization_id=api_key.project.organization_id,
        scopes=_scopes_for_key(api_key),
    )
    return principal, api_key


class ProjectApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[ProjectApiKeyPrincipal, ProjectApiKey] | None:
        authorization = get_authorization_header(request).split()
        if not authorization:
            return None
        if authorization[0].lower() != b"bearer":
            return None
        if len(authorization) != 2:
            raise _invalid_api_key()

        try:
            token = authorization[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise _invalid_api_key() from exc
        return authenticate_project_api_key(token)

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"


class HasProjectApiKeyScopes(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        principal = request.user
        if not isinstance(principal, ProjectApiKeyPrincipal):
            return False
        required_scopes = frozenset(getattr(view, "required_machine_scopes", ()))
        return required_scopes.issubset(principal.scopes)
