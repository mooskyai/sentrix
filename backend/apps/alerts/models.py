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


class AlertRuleState(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        OK = "ok", "ok"
        FIRING = "firing", "firing"
        NO_DATA = "no_data", "no data"
        ERROR = "error", "error"
        DISABLED = "disabled", "disabled"

    rule = models.OneToOneField(
        AlertRule,
        on_delete=models.CASCADE,
        related_name="evaluation_state",
        primary_key=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)
    state_changed_at = models.DateTimeField(null=True, blank=True)
    source_timestamp = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.rule}:{self.status}"


class NotificationChannel(models.Model):
    class ChannelType(models.TextChoices):
        WEBHOOK = "webhook", "Webhook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="notification_channels",
    )
    name = models.CharField(max_length=160)
    channel_type = models.CharField(
        max_length=16,
        choices=ChannelType.choices,
        default=ChannelType.WEBHOOK,
    )
    endpoint_url = models.URLField(max_length=2048)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notification_channels",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                name="uniq_notification_channel_name_per_project",
            )
        ]
        ordering = ["project_id", "name", "id"]

    def __str__(self) -> str:
        return f"{self.project}:{self.name}:{self.channel_type}"


class AlertNotificationDelivery(models.Model):
    class EventType(models.TextChoices):
        FIRING = "firing", "firing"
        RECOVERED = "recovered", "recovered"

    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        SENDING = "sending", "sending"
        RETRY = "retry", "retry"
        DELIVERED = "delivered", "delivered"
        FAILED = "failed", "failed"
        CANCELLED = "cancelled", "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    alert_rule_id = models.UUIDField()
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    state_changed_at = models.DateTimeField()
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "alert_rule_id", "event_type", "state_changed_at"],
                name="uniq_alert_notification_transition",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="alerts_delivery_due_idx",
            )
        ]
        ordering = ["channel_id", "created_at", "id"]

    def __str__(self) -> str:
        return f"{self.channel}:{self.alert_rule_id}:{self.event_type}:{self.status}"
