from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.telemetry.metrics_query import (
    AmbiguousLatestMetricPoint,
    query_latest_numeric_metric_point,
)

from .models import AlertRule, AlertRuleState
from .notifications import queue_alert_transition_deliveries

TIME_RANGE_DELTAS: dict[str, timedelta] = {
    AlertRule.TimeRange.ONE_HOUR.value: timedelta(hours=1),
    AlertRule.TimeRange.SIX_HOURS.value: timedelta(hours=6),
    AlertRule.TimeRange.TWENTY_FOUR_HOURS.value: timedelta(hours=24),
    AlertRule.TimeRange.SEVEN_DAYS.value: timedelta(days=7),
}

AMBIGUOUS_POINT_ERROR = "ambiguous_latest_point"
NON_FINITE_VALUE_ERROR = "non_finite_metric_value"
TELEMETRY_QUERY_ERROR = "telemetry_query_failed"


@dataclass(frozen=True, slots=True)
class AlertEvaluationResult:
    rule_id: UUID
    status: str
    changed: bool
    skipped: bool
    error_code: str


def _matches_threshold(comparator: str, value: float, threshold: float) -> bool:
    if comparator == AlertRule.Comparator.GREATER_THAN:
        return value > threshold
    if comparator == AlertRule.Comparator.GREATER_THAN_OR_EQUAL:
        return value >= threshold
    if comparator == AlertRule.Comparator.LESS_THAN:
        return value < threshold
    if comparator == AlertRule.Comparator.LESS_THAN_OR_EQUAL:
        return value <= threshold
    raise ValueError(f"Unsupported alert comparator: {comparator}")


def _normalized_evaluation_time(value: datetime | None) -> datetime:
    evaluation_time = value or timezone.now()
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=UTC)
    return evaluation_time.astimezone(UTC)


@transaction.atomic
def _persist_result(
    *,
    rule_id: UUID,
    expected_updated_at: datetime,
    status: str,
    evaluated_at: datetime,
    source_timestamp: datetime | None,
    error_code: str,
) -> AlertEvaluationResult:
    locked_rule = AlertRule.objects.select_for_update().get(pk=rule_id)
    state, _created = AlertRuleState.objects.select_for_update().get_or_create(
        rule=locked_rule,
        defaults={
            "status": (
                AlertRuleState.Status.PENDING
                if locked_rule.enabled
                else AlertRuleState.Status.DISABLED
            )
        },
    )

    newer_evaluation_exists = state.evaluated_at is not None and state.evaluated_at > evaluated_at
    if (
        locked_rule.updated_at != expected_updated_at
        or not locked_rule.enabled
        or newer_evaluation_exists
    ):
        if not locked_rule.enabled and state.status != AlertRuleState.Status.DISABLED:
            state.status = AlertRuleState.Status.DISABLED
            state.evaluated_at = None
            state.source_timestamp = None
            state.error_code = ""
            state.state_changed_at = evaluated_at
            state.save(
                update_fields=[
                    "status",
                    "evaluated_at",
                    "source_timestamp",
                    "error_code",
                    "state_changed_at",
                    "updated_at",
                ]
            )
        return AlertEvaluationResult(
            rule_id=locked_rule.id,
            status=state.status,
            changed=False,
            skipped=True,
            error_code=state.error_code,
        )

    previous_status = state.status
    changed = previous_status != status
    state.status = status
    state.evaluated_at = evaluated_at
    state.source_timestamp = source_timestamp
    state.error_code = error_code
    if changed:
        state.state_changed_at = evaluated_at
    state.save(
        update_fields=[
            "status",
            "evaluated_at",
            "source_timestamp",
            "error_code",
            "state_changed_at",
            "updated_at",
        ]
    )
    if changed:
        queue_alert_transition_deliveries(
            rule=locked_rule,
            previous_status=previous_status,
            next_status=state.status,
            evaluated_at=evaluated_at,
            source_timestamp=source_timestamp,
        )
    return AlertEvaluationResult(
        rule_id=locked_rule.id,
        status=state.status,
        changed=changed,
        skipped=False,
        error_code=state.error_code,
    )


def evaluate_alert_rule(
    *,
    rule_id: UUID,
    evaluated_at: datetime | None = None,
) -> AlertEvaluationResult:
    rule = AlertRule.objects.select_related("project", "project__organization").get(pk=rule_id)
    evaluation_time = _normalized_evaluation_time(evaluated_at)

    if not rule.enabled:
        return _persist_result(
            rule_id=rule.id,
            expected_updated_at=rule.updated_at,
            status=AlertRuleState.Status.DISABLED,
            evaluated_at=evaluation_time,
            source_timestamp=None,
            error_code="",
        )

    window = TIME_RANGE_DELTAS[rule.time_range]
    start = evaluation_time - window

    status = AlertRuleState.Status.ERROR
    source_timestamp: datetime | None = None
    error_code = ""
    try:
        point = query_latest_numeric_metric_point(
            organization_id=rule.project.organization_id,
            project_id=rule.project_id,
            metric_name=rule.metric_name,
            start=start,
            end=evaluation_time,
            service_name=rule.service_name or None,
            environment=rule.environment or None,
        )
    except AmbiguousLatestMetricPoint:
        error_code = AMBIGUOUS_POINT_ERROR
    except Exception:
        error_code = TELEMETRY_QUERY_ERROR
    else:
        if point is None:
            status = AlertRuleState.Status.NO_DATA
        elif not math.isfinite(point.value):
            error_code = NON_FINITE_VALUE_ERROR
        else:
            source_timestamp = point.timestamp
            status = (
                AlertRuleState.Status.FIRING
                if _matches_threshold(rule.comparator, point.value, rule.threshold)
                else AlertRuleState.Status.OK
            )

    return _persist_result(
        rule_id=rule.id,
        expected_updated_at=rule.updated_at,
        status=status,
        evaluated_at=evaluation_time,
        source_timestamp=source_timestamp,
        error_code=error_code,
    )


def evaluate_enabled_alert_rules(
    *,
    project_id: UUID | None = None,
    evaluated_at: datetime | None = None,
) -> list[AlertEvaluationResult]:
    evaluation_time = _normalized_evaluation_time(evaluated_at)
    rules = AlertRule.objects.filter(enabled=True).order_by("project_id", "id")
    if project_id is not None:
        rules = rules.filter(project_id=project_id)
    rule_ids = list(rules.values_list("id", flat=True))
    return [
        evaluate_alert_rule(rule_id=rule_id, evaluated_at=evaluation_time) for rule_id in rule_ids
    ]
