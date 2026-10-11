import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project


class AlertRule(models.Model):
    class TimeRange(models.TextChoices):
        ONE_HOUR = "1h", "1 hour"
        SIX_HOURS = "6h", "6 hours"
        TWENTY_FOUR_HOURS = "24h", "24 hours"
        SEVEN_DAYS = "7d", "7 days"

    class Comparator(models.TextChoices):
        GREATER_THAN = "gt", "greater than"
        GREATER_THAN_OR_EQUAL = "gte", "greater than or equal"
        LESS_THAN = "lt", "less than"
        LESS_THAN_OR_EQUAL = "lte", "less than or equal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    name = models.CharField(max_length=160)
    metric_name = models.CharField(max_length=512)
    time_range = models.CharField(
        max_length=3,
        choices=TimeRange.choices,
        default=TimeRange.ONE_HOUR,
    )
    service_name = models.CharField(max_length=512, blank=True, default="")
    environment = models.CharField(max_length=512, blank=True, default="")
    comparator = models.CharField(max_length=3, choices=Comparator.choices)
    threshold = models.FloatField()
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_alert_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                name="uniq_alert_rule_name_per_project",
            )
        ]
        ordering = ["project_id", "name", "id"]

    def __str__(self) -> str:
        return f"{self.project}:{self.name}"
