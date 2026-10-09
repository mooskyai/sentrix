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

from .logs_query import query_logs

DEFAULT_QUERY_WINDOW = timedelta(hours=1)
MAX_QUERY_WINDOW = timedelta(days=7)
LOG_DEFAULT_LIMIT = 200
LOG_MAX_LIMIT = 1_000


class TelemetryQueryUnavailable(APIException):
    status_code = 503
    default_detail = "Telemetry query service is unavailable."
    default_code = "telemetry_query_unavailable"


def _readable_project(request: Request, project_id: UUID) -> Project:
    user = request.user
    if not isinstance(user, User):
        raise PermissionDenied("Authentication is required.")
    try:
        return projects_for_user(user).select_related("organization").get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise NotFound("Project not found.") from exc


def _parse_datetime(raw: str | None, field_name: str) -> datetime | None:
    if raw is None:
        return None
    normalized = raw.strip()
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        value = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError({field_name: "Use an RFC3339 timestamp with timezone."}) from exc
    if value.tzinfo is None:
        raise ValidationError({field_name: "Timezone is required."})
    return value.astimezone(UTC)


def _query_window(request: Request) -> tuple[datetime, datetime]:
    end = _parse_datetime(request.query_params.get("end"), "end") or datetime.now(UTC)
    start = (
        _parse_datetime(request.query_params.get("start"), "start") or end - DEFAULT_QUERY_WINDOW
    )
    if start >= end:
        raise ValidationError({"start": "start must be earlier than end."})
    if end - start > MAX_QUERY_WINDOW:
        raise ValidationError({"start": "Log query windows may not exceed 7 days."})
    return start, end


def _bounded_limit(raw: str | None) -> int:
    if raw is None:
        return LOG_DEFAULT_LIMIT
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError({"limit": "limit must be an integer."}) from exc
    if value < 1 or value > LOG_MAX_LIMIT:
        raise ValidationError({"limit": f"limit must be between 1 and {LOG_MAX_LIMIT}."})
    return value


def _optional_text(request: Request, name: str, *, maximum: int = 512) -> str | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if len(value) > maximum:
        raise ValidationError({name: f"{name} may not exceed {maximum} characters."})
    return value


def _optional_min_severity(request: Request) -> int | None:
    raw = request.query_params.get("min_severity_number")
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(
            {"min_severity_number": "min_severity_number must be an integer."}
        ) from exc
    if value < 0 or value > 24:
        raise ValidationError(
            {"min_severity_number": "min_severity_number must be between 0 and 24."}
        )
    return value


def _optional_trace_id(request: Request) -> str | None:
    value = _optional_text(request, "trace_id", maximum=32)
    if value is None:
        return None
    normalized = value.lower()
    if len(normalized) != 32 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValidationError({"trace_id": "trace_id must be exactly 32 hexadecimal characters."})
    if set(normalized) == {"0"}:
        raise ValidationError({"trace_id": "trace_id must not be the all-zero identifier."})
    return normalized


def _api_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class LogSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        start, end = _query_window(request)
        limit = _bounded_limit(request.query_params.get("limit"))
        service_name = _optional_text(request, "service_name")
        environment = _optional_text(request, "environment")
        min_severity_number = _optional_min_severity(request)
        body_contains = _optional_text(request, "body_contains", maximum=512)
        trace_id = _optional_trace_id(request)

        try:
            logs, truncated = query_logs(
                organization_id=project.organization_id,
                project_id=project.id,
                start=start,
                end=end,
                limit=limit,
                service_name=service_name,
                environment=environment,
                min_severity_number=min_severity_number,
                body_contains=body_contains,
                trace_id=trace_id,
            )
        except Exception as exc:
            raise TelemetryQueryUnavailable() from exc

        return Response(
            {
                "project_id": str(project.id),
                "start": _api_timestamp(start),
                "end": _api_timestamp(end),
                "filters": {
                    "service_name": service_name,
                    "environment": environment,
                    "min_severity_number": min_severity_number,
                    "body_contains": body_contains,
                    "trace_id": trace_id,
                },
                "logs": logs,
                "truncated": truncated,
            }
        )
