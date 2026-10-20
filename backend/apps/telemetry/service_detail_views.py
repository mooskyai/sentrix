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

from .service_catalog_views import (
    DEFAULT_WINDOW,
    MAX_WINDOW,
    ServiceCatalogUnavailable,
    _datetime_param,
    _utc,
)
from .service_detail import query_service_detail


class ServiceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        user = request.user
        if not isinstance(user, User):
            raise PermissionDenied("Authentication is required.")
        try:
            project = projects_for_user(user).get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

        service_name = request.query_params.get("service_name")
        environment = request.query_params.get("environment")
        if service_name is None or not service_name or len(service_name) > 512:
            raise ValidationError(
                {"service_name": "A nonempty service_name of at most 512 characters is required."}
            )
        if environment is None or len(environment) > 512:
            raise ValidationError(
                {
                    "environment": (
                        "environment is required and may be empty (maximum 512 characters)."
                    )
                }
            )

        end = _datetime_param(request.query_params.get("end"), "end") or datetime.now(UTC)
        start = _datetime_param(request.query_params.get("start"), "start") or end - DEFAULT_WINDOW
        if start >= end or end - start > MAX_WINDOW:
            raise ValidationError({"start": "Window must be ordered and no longer than 7 days."})

        try:
            detail = query_service_detail(
                organization_id=project.organization_id,
                project_id=project.id,
                service_name=service_name,
                environment=environment,
                start=start,
                end=end,
            )
        except Exception as exc:
            raise ServiceCatalogUnavailable() from exc
        return Response(
            {
                "project_id": str(project.id),
                "service_name": service_name,
                "environment": environment,
                "start": _utc(start),
                "end": _utc(end),
                **detail,
            }
        )
