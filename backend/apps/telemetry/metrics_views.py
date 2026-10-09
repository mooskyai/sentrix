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

from .metrics_query import list_metric_catalog, query_numeric_metric_series

DEFAULT_QUERY_WINDOW = timedelta(hours=1)
MAX_QUERY_WINDOW = timedelta(days=7)
CATALOG_DEFAULT_LIMIT = 100
CATALOG_MAX_LIMIT = 500
SERIES_DEFAULT_LIMIT = 2_000
SERIES_MAX_LIMIT = 5_000


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
        raise ValidationError({"start": "Metric query windows may not exceed 7 days."})
    return start, end


def _bounded_limit(raw: str | None, *, default: int, maximum: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError({"limit": "limit must be an integer."}) from exc
    if value < 1 or value > maximum:
        raise ValidationError({"limit": f"limit must be between 1 and {maximum}."})
    return value


def _required_metric_name(request: Request) -> str:
    value = (request.query_params.get("metric_name") or "").strip()
    if not value:
        raise ValidationError({"metric_name": "metric_name is required."})
    if len(value) > 512:
        raise ValidationError({"metric_name": "metric_name may not exceed 512 characters."})
    return value


def _optional_dimension(request: Request, name: str) -> str | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if len(value) > 512:
        raise ValidationError({name: f"{name} may not exceed 512 characters."})
    return value


def _api_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class MetricCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        start, end = _query_window(request)
        limit = _bounded_limit(
            request.query_params.get("limit"),
            default=CATALOG_DEFAULT_LIMIT,
            maximum=CATALOG_MAX_LIMIT,
        )
        try:
            metrics = list_metric_catalog(
                organization_id=project.organization_id,
                project_id=project.id,
                start=start,
                end=end,
                limit=limit,
            )
        except Exception as exc:
            raise TelemetryQueryUnavailable() from exc
        return Response(
            {
                "project_id": str(project.id),
                "start": _api_timestamp(start),
                "end": _api_timestamp(end),
                "metrics": metrics,
            }
        )


class MetricSeriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        metric_name = _required_metric_name(request)
        start, end = _query_window(request)
        limit = _bounded_limit(
            request.query_params.get("limit"),
            default=SERIES_DEFAULT_LIMIT,
            maximum=SERIES_MAX_LIMIT,
        )
        service_name = _optional_dimension(request, "service_name")
        environment = _optional_dimension(request, "environment")
        try:
            points, truncated = query_numeric_metric_series(
                organization_id=project.organization_id,
                project_id=project.id,
                metric_name=metric_name,
                start=start,
                end=end,
                limit=limit,
                service_name=service_name,
                environment=environment,
            )
        except Exception as exc:
            raise TelemetryQueryUnavailable() from exc
        return Response(
            {
                "project_id": str(project.id),
                "metric_name": metric_name,
                "start": _api_timestamp(start),
                "end": _api_timestamp(end),
                "filters": {
                    "service_name": service_name,
                    "environment": environment,
                },
                "points": points,
                "truncated": truncated,
            }
        )
