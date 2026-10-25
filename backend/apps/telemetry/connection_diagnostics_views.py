"""Authenticated, member-only first-telemetry diagnostic endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.contrib.auth.models import User
from rest_framework import permissions
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.selectors import projects_for_user

from .connection_diagnostics import recent_signal_observations


class ConnectionDiagnosticsUnavailable(APIException):
    status_code = 503
    default_detail = "Telemetry query service is unavailable."
    default_code = "telemetry_query_unavailable"


class ConnectionDiagnosticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        user = request.user
        if not isinstance(user, User):
            raise PermissionDenied("Authentication is required.")
        try:
            project = projects_for_user(user).get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

        end = datetime.now(UTC)
        start = end - timedelta(hours=24)
        try:
            signals = recent_signal_observations(
                organization_id=project.organization_id,
                project_id=project.id,
                start=start,
                end=end,
            )
        except Exception as exc:
            raise ConnectionDiagnosticsUnavailable() from exc

        return Response(
            {
                "project_id": str(project.id),
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
                "signals": signals,
                "observation_state": (
                    "observed"
                    if any(item["observed"] for item in signals.values())
                    else "not_observed"
                ),
            }
        )
