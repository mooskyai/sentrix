from datetime import datetime
from secrets import token_hex, token_urlsafe

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max

from .models import Project, ProjectApiKey, ProjectDashboardPanel

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


MAX_PROJECT_DASHBOARD_PANELS = 6


class DashboardPanelLimitReached(Exception):
    pass


class DashboardPanelAlreadyExists(Exception):
    pass


@transaction.atomic
def create_project_dashboard_panel(
    *,
    project: Project,
    title: str,
    metric_name: str,
    time_range: str,
    service_name: str,
    environment: str,
    created_by: User,
) -> ProjectDashboardPanel:
    locked_project = Project.objects.select_for_update().get(pk=project.pk)
    panels = ProjectDashboardPanel.objects.filter(project=locked_project)
    if panels.count() >= MAX_PROJECT_DASHBOARD_PANELS:
        raise DashboardPanelLimitReached(
            f"A project may have at most {MAX_PROJECT_DASHBOARD_PANELS} dashboard panels."
        )
    if panels.filter(
        metric_name=metric_name,
        time_range=time_range,
        service_name=service_name,
        environment=environment,
    ).exists():
        raise DashboardPanelAlreadyExists(
            "A dashboard panel already uses this metric, range, and exact filters."
        )

    max_position = panels.aggregate(value=Max("position"))["value"]
    position = 0 if max_position is None else int(max_position) + 1
    return ProjectDashboardPanel.objects.create(
        project=locked_project,
        title=title,
        metric_name=metric_name,
        time_range=time_range,
        service_name=service_name,
        environment=environment,
        position=position,
        created_by=created_by,
    )
