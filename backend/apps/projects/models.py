import uuid

from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="uniq_project_slug_per_organization",
            )
        ]
        ordering = ["organization_id", "name", "id"]

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"


class ProjectApiKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=160)
    prefix = models.CharField(max_length=16, unique=True, editable=False)
    secret_hash = models.CharField(max_length=128, editable=False)
    scopes = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_api_keys",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project_id", "-created_at", "id"]

    def __str__(self) -> str:
        return f"{self.project}:{self.name}:{self.prefix}"


class ProjectDashboardPanel(models.Model):
    class TimeRange(models.TextChoices):
        ONE_HOUR = "1h", "1 hour"
        SIX_HOURS = "6h", "6 hours"
        TWENTY_FOUR_HOURS = "24h", "24 hours"
        SEVEN_DAYS = "7d", "7 days"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="dashboard_panels",
    )
    title = models.CharField(max_length=160)
    metric_name = models.CharField(max_length=512)
    time_range = models.CharField(
        max_length=3,
        choices=TimeRange.choices,
        default=TimeRange.ONE_HOUR,
    )
    service_name = models.CharField(max_length=512, blank=True, default="")
    environment = models.CharField(max_length=512, blank=True, default="")
    position = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_dashboard_panels",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "metric_name", "time_range", "service_name", "environment"],
                name="uniq_project_dashboard_panel_query",
            )
        ]
        ordering = ["project_id", "position", "created_at", "id"]

    def __str__(self) -> str:
        return f"{self.project}:{self.title}:{self.metric_name}"
