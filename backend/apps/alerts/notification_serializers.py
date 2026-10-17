from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from rest_framework import serializers

from .models import AlertNotificationDelivery, NotificationChannel
from .notification_channels import webhook_endpoint_error


class NotificationChannelSerializer(serializers.ModelSerializer[NotificationChannel]):
    project_id = serializers.UUIDField(read_only=True)
    endpoint_display = serializers.SerializerMethodField()

    class Meta:
        model = NotificationChannel
        fields = (
            "id",
            "project_id",
            "name",
            "channel_type",
            "endpoint_display",
            "enabled",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_endpoint_display(self, channel: NotificationChannel) -> str:
        parsed = urlsplit(channel.endpoint_url)
        return f"{parsed.scheme}://{parsed.netloc}/…"


class NotificationChannelWriteSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    endpoint_url = serializers.URLField(max_length=2048)
    enabled = serializers.BooleanField(default=True)

    def validate_endpoint_url(self, value: str) -> str:
        error = webhook_endpoint_error(value)
        if error is not None:
            raise serializers.ValidationError(error)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.partial and not attrs:
            raise serializers.ValidationError(
                "At least one notification-channel field is required."
            )
        return attrs


class AlertNotificationDeliverySerializer(serializers.ModelSerializer[AlertNotificationDelivery]):
    channel_name = serializers.CharField(source="channel.name", read_only=True)

    class Meta:
        model = AlertNotificationDelivery
        fields = (
            "id",
            "channel_id",
            "channel_name",
            "alert_rule_id",
            "event_type",
            "state_changed_at",
            "payload",
            "status",
            "attempt_count",
            "next_attempt_at",
            "last_attempt_at",
            "delivered_at",
            "response_status",
            "error_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
