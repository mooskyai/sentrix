# Generated manually for Sentrix V1 M5.4.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0002_alertrulestate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationChannel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                (
                    "channel_type",
                    models.CharField(
                        choices=[("webhook", "Webhook")],
                        default="webhook",
                        max_length=16,
                    ),
                ),
                ("endpoint_url", models.URLField(max_length=2048)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_notification_channels",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_channels",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ["project_id", "name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="notificationchannel",
            constraint=models.UniqueConstraint(
                fields=("project", "name"),
                name="uniq_notification_channel_name_per_project",
            ),
        ),
        migrations.CreateModel(
            name="AlertNotificationDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("alert_rule_id", models.UUIDField()),
                (
                    "event_type",
                    models.CharField(
                        choices=[("firing", "firing"), ("recovered", "recovered")],
                        max_length=16,
                    ),
                ),
                ("state_changed_at", models.DateTimeField()),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "pending"),
                            ("sending", "sending"),
                            ("retry", "retry"),
                            ("delivered", "delivered"),
                            ("failed", "failed"),
                            ("cancelled", "cancelled"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField()),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="alerts.notificationchannel",
                    ),
                ),
            ],
            options={"ordering": ["channel_id", "created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="alertnotificationdelivery",
            constraint=models.UniqueConstraint(
                fields=("channel", "alert_rule_id", "event_type", "state_changed_at"),
                name="uniq_alert_notification_transition",
            ),
        ),
        migrations.AddIndex(
            model_name="alertnotificationdelivery",
            index=models.Index(
                fields=["status", "next_attempt_at"],
                name="alerts_delivery_due_idx",
            ),
        ),
    ]
