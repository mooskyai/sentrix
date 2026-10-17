from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from apps.projects.models import Project

from .models import NotificationChannel

MAX_PROJECT_NOTIFICATION_CHANNELS = 10


class NotificationChannelLimitReached(Exception):
    pass


class NotificationChannelAlreadyExists(Exception):
    pass


def webhook_endpoint_error(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "Webhook endpoint URL is invalid."

    if not parsed.hostname:
        return "Webhook endpoint must include a hostname."
    if parsed.username is not None or parsed.password is not None:
        return "Webhook endpoint must not include user credentials."
    if parsed.query:
        return "Webhook endpoint must not include a query string."
    if parsed.fragment:
        return "Webhook endpoint must not include a fragment."

    allowed_schemes = {"https"}
    if settings.NOTIFICATION_WEBHOOK_ALLOW_HTTP:
        allowed_schemes.add("http")
    if parsed.scheme.lower() not in allowed_schemes:
        return "Webhook endpoint must use HTTPS."

    allowed_hosts = {
        host.lower().rstrip(".") for host in settings.NOTIFICATION_WEBHOOK_ALLOWED_HOSTS if host
    }
    hostname = parsed.hostname.lower().rstrip(".")
    if not allowed_hosts:
        return (
            "Webhook delivery is disabled until NOTIFICATION_WEBHOOK_ALLOWED_HOSTS is configured."
        )
    if hostname not in allowed_hosts:
        return "Webhook endpoint host is not allowed by server egress policy."
    return None


def derive_webhook_signing_secret(channel_id: object) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"sentrix:webhook-signing:{channel_id}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@transaction.atomic
def create_notification_channel(
    *,
    project: Project,
    name: str,
    endpoint_url: str,
    enabled: bool,
    created_by: User,
) -> NotificationChannel:
    locked_project = Project.objects.select_for_update().get(pk=project.pk)
    channels = NotificationChannel.objects.filter(project=locked_project)
    if channels.count() >= MAX_PROJECT_NOTIFICATION_CHANNELS:
        raise NotificationChannelLimitReached(
            f"A project may have at most {MAX_PROJECT_NOTIFICATION_CHANNELS} notification channels."
        )
    if channels.filter(name=name).exists():
        raise NotificationChannelAlreadyExists(
            "A notification channel with this name already exists in the project."
        )
    return NotificationChannel.objects.create(
        project=locked_project,
        name=name,
        channel_type=NotificationChannel.ChannelType.WEBHOOK,
        endpoint_url=endpoint_url,
        enabled=enabled,
        created_by=created_by,
    )


@transaction.atomic
def update_notification_channel(
    *,
    channel: NotificationChannel,
    name: str | None = None,
    endpoint_url: str | None = None,
    enabled: bool | None = None,
) -> NotificationChannel:
    locked_project = Project.objects.select_for_update().get(pk=channel.project_id)
    locked_channel = NotificationChannel.objects.select_for_update().get(
        pk=channel.pk,
        project=locked_project,
    )
    next_name = locked_channel.name if name is None else name
    if (
        NotificationChannel.objects.filter(project=locked_project, name=next_name)
        .exclude(pk=locked_channel.pk)
        .exists()
    ):
        raise NotificationChannelAlreadyExists(
            "A notification channel with this name already exists in the project."
        )

    update_fields: list[str] = []
    values: tuple[tuple[str, object | None], ...] = (
        ("name", name),
        ("endpoint_url", endpoint_url),
        ("enabled", enabled),
    )
    for field_name, value in values:
        if value is not None:
            setattr(locked_channel, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        locked_channel.save(update_fields=[*update_fields, "updated_at"])
    return locked_channel
