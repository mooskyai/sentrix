from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AlertNotificationDelivery, AlertRule, AlertRuleState, NotificationChannel
from .notification_channels import derive_webhook_signing_secret, webhook_endpoint_error

MAX_DELIVERY_ATTEMPTS = 3
CLAIM_LEASE = timedelta(minutes=2)
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5))


@dataclass(frozen=True, slots=True)
class NotificationDispatchResult:
    delivery_id: UUID
    status: str
    attempt_count: int
    response_status: int | None
    error_code: str
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class _DeliveryClaim:
    delivery_id: UUID
    lease_token: UUID
    channel_id: UUID
    endpoint_url: str
    event_type: str
    payload: dict[str, Any]
    attempt_count: int


@dataclass(frozen=True, slots=True)
class _AttemptResult:
    response_status: int | None
    error_code: str
    retryable: bool


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _transition_event(previous_status: str, next_status: str) -> str | None:
    if (
        next_status == AlertRuleState.Status.FIRING
        and previous_status != AlertRuleState.Status.FIRING
    ):
        return AlertNotificationDelivery.EventType.FIRING
    if previous_status == AlertRuleState.Status.FIRING and next_status == AlertRuleState.Status.OK:
        return AlertNotificationDelivery.EventType.RECOVERED
    return None


def queue_alert_transition_deliveries(
    *,
    rule: AlertRule,
    previous_status: str,
    next_status: str,
    evaluated_at: datetime,
    source_timestamp: datetime | None,
) -> int:
    event_type = _transition_event(previous_status, next_status)
    if event_type is None:
        return 0

    channels = list(
        NotificationChannel.objects.filter(project_id=rule.project_id, enabled=True).only("id")
    )
    if not channels:
        return 0

    payload = {
        "version": 1,
        "event": f"sentrix.alert.{event_type}",
        "project_id": str(rule.project_id),
        "alert_rule": {
            "id": str(rule.id),
            "name": rule.name,
            "metric_name": rule.metric_name,
            "time_range": rule.time_range,
            "service_name": rule.service_name,
            "environment": rule.environment,
            "comparator": rule.comparator,
            "threshold": rule.threshold,
        },
        "state": {
            "status": next_status,
            "evaluated_at": _iso(evaluated_at),
            "state_changed_at": _iso(evaluated_at),
            "source_timestamp": _iso(source_timestamp),
        },
    }
    due_at = timezone.now()
    AlertNotificationDelivery.objects.bulk_create(
        [
            AlertNotificationDelivery(
                channel=channel,
                alert_rule_id=rule.id,
                event_type=event_type,
                state_changed_at=evaluated_at,
                payload=payload,
                next_attempt_at=due_at,
            )
            for channel in channels
        ]
    )
    return len(channels)


def _request_for_claim(claim: _DeliveryClaim, *, sent_at: datetime) -> Request:
    body = json.dumps(claim.payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = str(int(sent_at.timestamp()))
    secret = derive_webhook_signing_secret(claim.channel_id)
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return Request(
        claim.endpoint_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Sentrix-Webhook/1",
            "X-Sentrix-Delivery": str(claim.delivery_id),
            "X-Sentrix-Event": f"alert.{claim.event_type}",
            "X-Sentrix-Timestamp": timestamp,
            "X-Sentrix-Signature": f"sha256={signature}",
        },
    )


def _perform_webhook_attempt(claim: _DeliveryClaim) -> _AttemptResult:
    endpoint_error = webhook_endpoint_error(claim.endpoint_url)
    if endpoint_error is not None:
        return _AttemptResult(
            response_status=None,
            error_code="endpoint_not_allowed",
            retryable=False,
        )

    request = _request_for_claim(claim, sent_at=timezone.now())
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(
            request, timeout=settings.NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS
        ) as response:
            status_code = int(response.status)
    except HTTPError as exc:
        return _AttemptResult(
            response_status=exc.code,
            error_code="http_status",
            retryable=exc.code in {408, 425, 429} or 500 <= exc.code < 600,
        )
    except TimeoutError:
        return _AttemptResult(response_status=None, error_code="timeout", retryable=True)
    except URLError:
        return _AttemptResult(response_status=None, error_code="network_error", retryable=True)
    except OSError:
        return _AttemptResult(response_status=None, error_code="network_error", retryable=True)

    if 200 <= status_code < 300:
        return _AttemptResult(response_status=status_code, error_code="", retryable=False)
    return _AttemptResult(
        response_status=status_code,
        error_code="http_status",
        retryable=status_code in {408, 425, 429} or 500 <= status_code < 600,
    )


@transaction.atomic
def _claim_next_delivery(
    *,
    project_id: UUID | None,
    now: datetime,
) -> tuple[_DeliveryClaim | None, NotificationDispatchResult | None]:
    due = Q(
        status__in=[
            AlertNotificationDelivery.Status.PENDING,
            AlertNotificationDelivery.Status.RETRY,
        ],
        next_attempt_at__lte=now,
    ) | Q(
        status=AlertNotificationDelivery.Status.SENDING,
        lease_expires_at__lte=now,
    )
    deliveries = (
        AlertNotificationDelivery.objects.select_for_update(skip_locked=True)
        .select_related("channel")
        .filter(due)
        .order_by("next_attempt_at", "created_at", "id")
    )
    if project_id is not None:
        deliveries = deliveries.filter(channel__project_id=project_id)
    delivery = deliveries.first()
    if delivery is None:
        return None, None

    if not delivery.channel.enabled:
        delivery.status = AlertNotificationDelivery.Status.CANCELLED
        delivery.error_code = "channel_disabled"
        delivery.lease_token = None
        delivery.lease_expires_at = None
        delivery.save(
            update_fields=[
                "status",
                "error_code",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return None, NotificationDispatchResult(
            delivery_id=delivery.id,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            response_status=delivery.response_status,
            error_code=delivery.error_code,
        )

    if delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
        delivery.status = AlertNotificationDelivery.Status.FAILED
        delivery.error_code = "lease_expired"
        delivery.lease_token = None
        delivery.lease_expires_at = None
        delivery.save(
            update_fields=[
                "status",
                "error_code",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return None, NotificationDispatchResult(
            delivery_id=delivery.id,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            response_status=delivery.response_status,
            error_code=delivery.error_code,
        )

    lease_token = uuid4()
    delivery.status = AlertNotificationDelivery.Status.SENDING
    delivery.attempt_count += 1
    delivery.last_attempt_at = now
    delivery.lease_token = lease_token
    delivery.lease_expires_at = now + CLAIM_LEASE
    delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "last_attempt_at",
            "lease_token",
            "lease_expires_at",
            "updated_at",
        ]
    )
    return (
        _DeliveryClaim(
            delivery_id=delivery.id,
            lease_token=lease_token,
            channel_id=delivery.channel_id,
            endpoint_url=delivery.channel.endpoint_url,
            event_type=delivery.event_type,
            payload=dict(delivery.payload),
            attempt_count=delivery.attempt_count,
        ),
        None,
    )


@transaction.atomic
def _finish_claim(
    *,
    claim: _DeliveryClaim,
    attempt: _AttemptResult,
    finished_at: datetime,
) -> NotificationDispatchResult:
    delivery = AlertNotificationDelivery.objects.select_for_update().get(pk=claim.delivery_id)
    if (
        delivery.status != AlertNotificationDelivery.Status.SENDING
        or delivery.lease_token != claim.lease_token
    ):
        return NotificationDispatchResult(
            delivery_id=delivery.id,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            response_status=delivery.response_status,
            error_code=delivery.error_code,
            skipped=True,
        )

    delivery.response_status = attempt.response_status
    delivery.lease_token = None
    delivery.lease_expires_at = None
    if attempt.error_code == "" and attempt.response_status is not None:
        delivery.status = AlertNotificationDelivery.Status.DELIVERED
        delivery.delivered_at = finished_at
        delivery.error_code = ""
    elif not attempt.retryable or delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
        delivery.status = AlertNotificationDelivery.Status.FAILED
        delivery.error_code = attempt.error_code or "delivery_failed"
    else:
        delivery.status = AlertNotificationDelivery.Status.RETRY
        delivery.error_code = attempt.error_code or "delivery_failed"
        delay_index = min(delivery.attempt_count - 1, len(RETRY_DELAYS) - 1)
        delivery.next_attempt_at = finished_at + RETRY_DELAYS[delay_index]

    delivery.save(
        update_fields=[
            "status",
            "next_attempt_at",
            "lease_token",
            "lease_expires_at",
            "delivered_at",
            "response_status",
            "error_code",
            "updated_at",
        ]
    )
    return NotificationDispatchResult(
        delivery_id=delivery.id,
        status=delivery.status,
        attempt_count=delivery.attempt_count,
        response_status=delivery.response_status,
        error_code=delivery.error_code,
    )


def dispatch_due_notifications(
    *,
    project_id: UUID | None = None,
    limit: int = 100,
) -> list[NotificationDispatchResult]:
    if not 1 <= limit <= 1000:
        raise ValueError("Notification dispatch limit must be between 1 and 1000.")

    results: list[NotificationDispatchResult] = []
    while len(results) < limit:
        now = timezone.now()
        claim, terminal = _claim_next_delivery(project_id=project_id, now=now)
        if terminal is not None:
            results.append(terminal)
            continue
        if claim is None:
            break
        attempt = _perform_webhook_attempt(claim)
        results.append(
            _finish_claim(
                claim=claim,
                attempt=attempt,
                finished_at=timezone.now(),
            )
        )
    return results
