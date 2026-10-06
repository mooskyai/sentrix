from datetime import datetime
from secrets import token_hex, token_urlsafe

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from .models import Project, ProjectApiKey

API_KEY_TOKEN_PREFIX = "sentrix_pk"
TELEMETRY_WRITE_SCOPE = "telemetry:write"


def create_project_api_key(
    *,
    project: Project,
    name: str,
    created_by: User,
    expires_at: datetime | None = None,
) -> tuple[ProjectApiKey, str]:
    public_prefix = token_hex(6)
    secret = token_urlsafe(32)
    api_key = ProjectApiKey.objects.create(
        project=project,
        name=name,
        prefix=public_prefix,
        secret_hash=make_password(secret),
        scopes=[TELEMETRY_WRITE_SCOPE],
        created_by=created_by,
        expires_at=expires_at,
    )
    token = f"{API_KEY_TOKEN_PREFIX}_{public_prefix}_{secret}"
    return api_key, token
