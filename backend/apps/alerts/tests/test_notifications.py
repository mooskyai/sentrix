from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from http.client import HTTPMessage
from typing import Any
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.alerts import evaluation, notifications
from apps.alerts.models import (
    AlertNotificationDelivery,
    AlertRule,
    AlertRuleState,
    NotificationChannel,
)
from apps.alerts.notification_channels import (
    MAX_PROJECT_NOTIFICATION_CHANNELS,
    create_notification_channel,
    derive_webhook_signing_secret,
)
from apps.alerts.services import create_alert_rule
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.telemetry.metrics_query import LatestNumericMetricPoint


def _owner_project(prefix: str) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User.objects.create_user(username=f"{prefix}-{suffix}")
    organization = Organization.objects.create(
        name=f"{prefix} organization",
        slug=f"{prefix}-{suffix}",
    )
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.OWNER,
    )
    project = Project.objects.create(
        organization=organization,
        name=f"{prefix} project",
        slug="app",
        created_by=user,
    )
    return user, project


def _rule(owner: User, project: Project) -> AlertRule:
    return create_alert_rule(
        project=project,
        name="Checkout latency",
        metric_name="checkout.duration",
        time_range=AlertRule.TimeRange.ONE_HOUR,
        service_name="checkout",
        environment="production",
        comparator=AlertRule.Comparator.GREATER_THAN,
        threshold=10.0,
        enabled=True,
        created_by=owner,
    )


def _channel(owner: User, project: Project, *, enabled: bool = True) -> NotificationChannel:
    return create_notification_channel(
        project=project,
        name="Primary webhook",
        endpoint_url="https://hooks.example.com/sentrix",
        enabled=enabled,
        created_by=owner,
    )


@pytest.fixture(autouse=True)
def _notification_settings(settings: Any) -> None:
    settings.NOTIFICATION_WEBHOOK_ALLOWED_HOSTS = ["hooks.example.com"]
    settings.NOTIFICATION_WEBHOOK_ALLOW_HTTP = False
    settings.NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS = 1.0


@pytest.mark.django_db
class TestNotificationChannelApi:
    def test_create_returns_signing_secret_once_and_redacts_endpoint(self) -> None:
        owner, project = _owner_project("notification-create")
        client = APIClient()
        client.force_authenticate(user=owner)

        response = client.post(
            f"/api/v1/projects/{project.id}/notification-channels/",
            {
                "name": "Operations webhook",
                "endpoint_url": "https://hooks.example.com/private/token",
                "enabled": True,
            },
            format="json",
        )

        assert response.status_code == 201
        body = response.json()
        assert body["signing_secret"]
        assert body["endpoint_display"] == "https://hooks.example.com/…"
        assert "endpoint_url" not in body

        listed = client.get(f"/api/v1/projects/{project.id}/notification-channels/")
        assert listed.status_code == 200
        assert "signing_secret" not in listed.json()[0]
        assert "endpoint_url" not in listed.json()[0]
        channel = NotificationChannel.objects.get(pk=body["id"])
        assert channel.endpoint_url == "https://hooks.example.com/private/token"

    def test_viewer_is_read_only(self) -> None:
        owner, project = _owner_project("notification-viewer")
        viewer = User.objects.create_user(username=f"viewer-{uuid4().hex[:8]}")
        OrganizationMembership.objects.create(
            organization=project.organization,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )
        _channel(owner, project)
        client = APIClient()
        client.force_authenticate(user=viewer)

        listed = client.get(f"/api/v1/projects/{project.id}/notification-channels/")
        created = client.post(
            f"/api/v1/projects/{project.id}/notification-channels/",
            {
                "name": "Denied",
                "endpoint_url": "https://hooks.example.com/denied",
                "enabled": True,
            },
            format="json",
        )

        assert listed.status_code == 200
        assert created.status_code == 403

    def test_foreign_project_is_not_discoverable(self) -> None:
        owner_a, _project_a = _owner_project("notification-tenant-a")
        _owner_b, project_b = _owner_project("notification-tenant-b")
        client = APIClient()
        client.force_authenticate(user=owner_a)

        response = client.get(f"/api/v1/projects/{project_b.id}/notification-channels/")

        assert response.status_code == 404

    def test_duplicate_name_and_project_cap_are_rejected(self) -> None:
        owner, project = _owner_project("notification-bounds")
        client = APIClient()
        client.force_authenticate(user=owner)
        for index in range(MAX_PROJECT_NOTIFICATION_CHANNELS):
            response = client.post(
                f"/api/v1/projects/{project.id}/notification-channels/",
                {
                    "name": f"Channel {index}",
                    "endpoint_url": f"https://hooks.example.com/{index}",
                    "enabled": True,
                },
                format="json",
            )
            assert response.status_code == 201

        duplicate = client.post(
            f"/api/v1/projects/{project.id}/notification-channels/",
            {
                "name": "Channel 0",
                "endpoint_url": "https://hooks.example.com/duplicate",
                "enabled": True,
            },
            format="json",
        )
        over_limit = client.post(
            f"/api/v1/projects/{project.id}/notification-channels/",
            {
                "name": "Channel 11",
                "endpoint_url": "https://hooks.example.com/overflow",
                "enabled": True,
            },
            format="json",
        )

        assert duplicate.status_code == 400
        assert over_limit.status_code == 400
        assert (
            NotificationChannel.objects.filter(project=project).count()
            == MAX_PROJECT_NOTIFICATION_CHANNELS
        )

    def test_unapproved_webhook_host_is_rejected(self) -> None:
        owner, project = _owner_project("notification-egress")
        client = APIClient()
        client.force_authenticate(user=owner)

        response = client.post(
            f"/api/v1/projects/{project.id}/notification-channels/",
            {
                "name": "Bad egress",
                "endpoint_url": "https://internal.example.test/hook",
                "enabled": True,
            },
            format="json",
        )

        assert response.status_code == 400
        assert NotificationChannel.objects.filter(project=project).count() == 0


@pytest.mark.django_db
class TestNotificationDelivery:
    def test_firing_and_recovery_transitions_enqueue_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("notification-transition")
        rule = _rule(owner, project)
        _channel(owner, project)
        values = iter([12.0, 13.0, 5.0])

        def fake_latest(**_kwargs: Any) -> LatestNumericMetricPoint:
            return LatestNumericMetricPoint(
                timestamp=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
                value=next(values),
            )

        monkeypatch.setattr(evaluation, "query_latest_numeric_metric_point", fake_latest)
        first = datetime(2026, 10, 17, 12, 1, tzinfo=UTC)
        evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=first)
        evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=first + timedelta(minutes=1))
        evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=first + timedelta(minutes=2))

        deliveries = list(AlertNotificationDelivery.objects.order_by("created_at"))
        assert [delivery.event_type for delivery in deliveries] == ["firing", "recovered"]
        assert deliveries[0].payload["state"]["status"] == AlertRuleState.Status.FIRING
        assert deliveries[1].payload["state"]["status"] == AlertRuleState.Status.OK
        assert deliveries[0].payload["alert_rule"]["threshold"] == 10.0
        assert "observed_value" not in deliveries[0].payload

    def test_successful_dispatch_signs_payload_and_persists_delivery(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("notification-success")
        rule = _rule(owner, project)
        channel = _channel(owner, project)
        delivery = AlertNotificationDelivery.objects.create(
            channel=channel,
            alert_rule_id=rule.id,
            event_type=AlertNotificationDelivery.EventType.FIRING,
            state_changed_at=timezone.now(),
            payload={"event": "sentrix.alert.firing", "version": 1},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        captured: dict[str, Any] = {}

        class Response:
            status = 204

            def __enter__(self) -> Response:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        class Opener:
            def open(self, request: Any, *, timeout: float) -> Response:
                captured["request"] = request
                captured["timeout"] = timeout
                return Response()

        monkeypatch.setattr(notifications, "build_opener", lambda *_handlers: Opener())

        results = notifications.dispatch_due_notifications(project_id=project.id)

        assert len(results) == 1
        assert results[0].status == AlertNotificationDelivery.Status.DELIVERED
        delivery.refresh_from_db()
        assert delivery.status == AlertNotificationDelivery.Status.DELIVERED
        assert delivery.attempt_count == 1
        assert delivery.response_status == 204
        request = captured["request"]
        timestamp = request.get_header("X-sentrix-timestamp")
        body = request.data
        assert isinstance(timestamp, str)
        assert isinstance(body, bytes)
        secret = derive_webhook_signing_secret(channel.id)
        expected = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        assert request.get_header("X-sentrix-signature") == f"sha256={expected}"
        assert json.loads(body)["event"] == "sentrix.alert.firing"
        assert captured["timeout"] == 1.0

    def test_transient_failure_retries_then_becomes_terminal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("notification-retry")
        rule = _rule(owner, project)
        channel = _channel(owner, project)
        delivery = AlertNotificationDelivery.objects.create(
            channel=channel,
            alert_rule_id=rule.id,
            event_type=AlertNotificationDelivery.EventType.FIRING,
            state_changed_at=timezone.now(),
            payload={"event": "sentrix.alert.firing", "version": 1},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

        class Opener:
            def open(self, request: Any, *, timeout: float) -> Any:
                raise URLError("offline")

        monkeypatch.setattr(notifications, "build_opener", lambda *_handlers: Opener())

        first = notifications.dispatch_due_notifications(project_id=project.id)
        delivery.refresh_from_db()
        assert first[0].status == AlertNotificationDelivery.Status.RETRY
        assert delivery.attempt_count == 1
        assert delivery.error_code == "network_error"

        for expected_attempt in (2, 3):
            delivery.next_attempt_at = timezone.now() - timedelta(seconds=1)
            delivery.save(update_fields=["next_attempt_at", "updated_at"])
            result = notifications.dispatch_due_notifications(project_id=project.id)
            delivery.refresh_from_db()
            assert delivery.attempt_count == expected_attempt
            if expected_attempt < 3:
                assert result[0].status == AlertNotificationDelivery.Status.RETRY
            else:
                assert result[0].status == AlertNotificationDelivery.Status.FAILED
                assert delivery.status == AlertNotificationDelivery.Status.FAILED

    def test_non_retryable_http_failure_is_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner, project = _owner_project("notification-terminal")
        rule = _rule(owner, project)
        channel = _channel(owner, project)
        delivery = AlertNotificationDelivery.objects.create(
            channel=channel,
            alert_rule_id=rule.id,
            event_type=AlertNotificationDelivery.EventType.FIRING,
            state_changed_at=timezone.now(),
            payload={"event": "sentrix.alert.firing", "version": 1},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

        class Opener:
            def open(self, request: Any, *, timeout: float) -> Any:
                raise HTTPError(request.full_url, 400, "bad request", hdrs=HTTPMessage(), fp=None)

        monkeypatch.setattr(notifications, "build_opener", lambda *_handlers: Opener())

        result = notifications.dispatch_due_notifications(project_id=project.id)

        delivery.refresh_from_db()
        assert result[0].status == AlertNotificationDelivery.Status.FAILED
        assert delivery.attempt_count == 1
        assert delivery.response_status == 400
        assert delivery.error_code == "http_status"

    def test_stale_delivery_completion_cannot_overwrite_reclaimed_lease(self) -> None:
        owner, project = _owner_project("notification-lease")
        rule = _rule(owner, project)
        channel = _channel(owner, project)
        delivery = AlertNotificationDelivery.objects.create(
            channel=channel,
            alert_rule_id=rule.id,
            event_type=AlertNotificationDelivery.EventType.FIRING,
            state_changed_at=timezone.now(),
            payload={"event": "sentrix.alert.firing", "version": 1},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        first_claim, first_terminal = notifications._claim_next_delivery(
            project_id=project.id,
            now=timezone.now(),
        )
        assert first_terminal is None
        assert first_claim is not None

        delivery.refresh_from_db()
        delivery.lease_expires_at = timezone.now() - timedelta(seconds=1)
        delivery.save(update_fields=["lease_expires_at", "updated_at"])
        second_claim, second_terminal = notifications._claim_next_delivery(
            project_id=project.id,
            now=timezone.now(),
        )
        assert second_terminal is None
        assert second_claim is not None
        assert second_claim.lease_token != first_claim.lease_token

        stale = notifications._finish_claim(
            claim=first_claim,
            attempt=notifications._AttemptResult(
                response_status=204,
                error_code="",
                retryable=False,
            ),
            finished_at=timezone.now(),
        )

        delivery.refresh_from_db()
        assert stale.skipped is True
        assert delivery.status == AlertNotificationDelivery.Status.SENDING
        assert delivery.lease_token == second_claim.lease_token

    def test_disabled_channel_cancels_pending_delivery(self) -> None:
        owner, project = _owner_project("notification-disabled")
        rule = _rule(owner, project)
        channel = _channel(owner, project, enabled=False)
        delivery = AlertNotificationDelivery.objects.create(
            channel=channel,
            alert_rule_id=rule.id,
            event_type=AlertNotificationDelivery.EventType.FIRING,
            state_changed_at=timezone.now(),
            payload={"event": "sentrix.alert.firing", "version": 1},
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

        results = notifications.dispatch_due_notifications(project_id=project.id)

        delivery.refresh_from_db()
        assert results[0].status == AlertNotificationDelivery.Status.CANCELLED
        assert delivery.status == AlertNotificationDelivery.Status.CANCELLED
        assert delivery.attempt_count == 0
        assert delivery.error_code == "channel_disabled"
