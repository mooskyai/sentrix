from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from django.contrib.auth.models import User
from rest_framework import permissions
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.selectors import projects_for_user

from .infrastructure import (
    DEFAULT_INFRASTRUCTURE_LIMIT,
    MAX_INFRASTRUCTURE_LIMIT,
    query_infrastructure,
)
from .service_catalog_views import (
    DEFAULT_WINDOW,
    MAX_WINDOW,
    ServiceCatalogUnavailable,
    _datetime_param,
    _utc,
)


class InfrastructureView(APIView):
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
            limit = DEFAULT_INFRASTRUCTURE_LIMIT if raw_limit is None else int(raw_limit)
        except ValueError as exc:
            raise ValidationError({"limit": "limit must be an integer."}) from exc
        if not 1 <= limit <= MAX_INFRASTRUCTURE_LIMIT:
            raise ValidationError({"limit": "limit must be between 1 and 500."})

        try:
            observations, truncated = query_infrastructure(
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
                "observations": observations,
            }
        )
