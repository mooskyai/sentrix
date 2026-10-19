from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.contrib.auth.models import User
from rest_framework import permissions
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.selectors import projects_for_user

from .service_catalog import MAX_SERVICE_CATALOG_LIMIT, list_observed_services

DEFAULT_WINDOW = timedelta(hours=24)
MAX_WINDOW = timedelta(days=7)
DEFAULT_LIMIT = 100


class ServiceCatalogUnavailable(APIException):
    status_code = 503
    default_detail = "Telemetry query service is unavailable."
    default_code = "telemetry_query_unavailable"


def _datetime_param(raw: str | None, name: str) -> datetime | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.endswith(("Z", "z")):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: "Use an RFC3339 timestamp with timezone."}) from exc
    if parsed.tzinfo is None:
        raise ValidationError({name: "Timezone is required."})
    return parsed.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ServiceCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        user = request.user
        if not isinstance(user, User):
            raise PermissionDenied("Authentication is required.")
        try:
            project = projects_for_user(user).get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

        end = _datetime_param(request.query_params.get("end"), "end") or datetime.now(UTC)
        start = _datetime_param(request.query_params.get("start"), "start") or end - DEFAULT_WINDOW
        if start >= end or end - start > MAX_WINDOW:
            raise ValidationError({"start": "Window must be ordered and no longer than 7 days."})

        raw_limit = request.query_params.get("limit")
        try:
            limit = DEFAULT_LIMIT if raw_limit is None else int(raw_limit)
        except ValueError as exc:
            raise ValidationError({"limit": "limit must be an integer."}) from exc
        if limit < 1 or limit > MAX_SERVICE_CATALOG_LIMIT:
            raise ValidationError({"limit": "limit must be between 1 and 500."})

        try:
            services, truncated = list_observed_services(
                organization_id=project.organization_id,
                project_id=project.id,
                start=start,
                end=end,
                limit=limit,
            )
        except Exception as exc:
            raise ServiceCatalogUnavailable() from exc
        return Response(
            {
                "project_id": str(project.id),
                "start": _utc(start),
                "end": _utc(end),
                "limit": limit,
                "truncated": truncated,
                "services": services,
            }
        )
