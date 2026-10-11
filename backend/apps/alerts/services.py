from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from apps.projects.models import Project

from .models import AlertRule, AlertRuleState

MAX_PROJECT_ALERT_RULES = 50


class AlertRuleLimitReached(Exception):
    pass


class AlertRuleAlreadyExists(Exception):
    pass


def _reset_alert_rule_state(rule: AlertRule, status: str) -> None:
    state, _created = AlertRuleState.objects.get_or_create(
        rule=rule,
        defaults={"status": status},
    )
    changed = state.status != status
    state.status = status
    state.evaluated_at = None
    state.source_timestamp = None
    state.error_code = ""
    if changed:
        state.state_changed_at = timezone.now()
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


@transaction.atomic
def create_alert_rule(
    *,
    project: Project,
    name: str,
    metric_name: str,
    time_range: str,
    service_name: str,
    environment: str,
    comparator: str,
    threshold: float,
    enabled: bool,
    created_by: User,
) -> AlertRule:
    locked_project = Project.objects.select_for_update().get(pk=project.pk)
    rules = AlertRule.objects.filter(project=locked_project)
    if rules.count() >= MAX_PROJECT_ALERT_RULES:
        raise AlertRuleLimitReached(
            f"A project may have at most {MAX_PROJECT_ALERT_RULES} alert rules."
        )
    if rules.filter(name=name).exists():
        raise AlertRuleAlreadyExists("An alert rule with this name already exists in the project.")

    rule = AlertRule.objects.create(
        project=locked_project,
        name=name,
        metric_name=metric_name,
        time_range=time_range,
        service_name=service_name,
        environment=environment,
        comparator=comparator,
        threshold=threshold,
        enabled=enabled,
        created_by=created_by,
    )
    AlertRuleState.objects.create(
        rule=rule,
        status=AlertRuleState.Status.PENDING if enabled else AlertRuleState.Status.DISABLED,
    )
    return rule


@transaction.atomic
def update_alert_rule(
    *,
    rule: AlertRule,
    name: str | None = None,
    metric_name: str | None = None,
    time_range: str | None = None,
    service_name: str | None = None,
    environment: str | None = None,
    comparator: str | None = None,
    threshold: float | None = None,
    enabled: bool | None = None,
) -> AlertRule:
    locked_project = Project.objects.select_for_update().get(pk=rule.project_id)
    locked_rule = AlertRule.objects.select_for_update().get(
        pk=rule.pk,
        project=locked_project,
    )
    next_name = locked_rule.name if name is None else name
    if (
        AlertRule.objects.filter(project=locked_project, name=next_name)
        .exclude(pk=locked_rule.pk)
        .exists()
    ):
        raise AlertRuleAlreadyExists("An alert rule with this name already exists in the project.")

    was_enabled = locked_rule.enabled
    evaluation_config_changed = any(
        value is not None
        for value in (
            metric_name,
            time_range,
            service_name,
            environment,
            comparator,
            threshold,
        )
    )

    update_fields: list[str] = []
    values: tuple[tuple[str, object | None], ...] = (
        ("name", name),
        ("metric_name", metric_name),
        ("time_range", time_range),
        ("service_name", service_name),
        ("environment", environment),
        ("comparator", comparator),
        ("threshold", threshold),
        ("enabled", enabled),
    )
    for field_name, value in values:
        if value is not None:
            setattr(locked_rule, field_name, value)
            update_fields.append(field_name)

    locked_rule.save(update_fields=[*update_fields, "updated_at"])

    enabled_changed = enabled is not None and locked_rule.enabled != was_enabled
    if not locked_rule.enabled:
        if enabled_changed or evaluation_config_changed:
            _reset_alert_rule_state(locked_rule, AlertRuleState.Status.DISABLED)
    elif enabled_changed or evaluation_config_changed:
        _reset_alert_rule_state(locked_rule, AlertRuleState.Status.PENDING)

    return locked_rule
