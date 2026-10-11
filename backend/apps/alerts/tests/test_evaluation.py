from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.alerts import evaluation
from apps.alerts.models import AlertRule, AlertRuleState
from apps.alerts.services import create_alert_rule, update_alert_rule
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.telemetry import metrics_query
from apps.telemetry.metrics_query import (
    AmbiguousLatestMetricPoint,
    LatestNumericMetricPoint,
)


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


def _rule(
    *,
    owner: User,
    project: Project,
    name: str = "CPU high",
    comparator: str = AlertRule.Comparator.GREATER_THAN,
    threshold: float = 10.0,
    time_range: str = AlertRule.TimeRange.ONE_HOUR,
    enabled: bool = True,
) -> AlertRule:
    return create_alert_rule(
        project=project,
        name=name,
        metric_name="process.cpu.utilization",
        time_range=time_range,
        service_name="api",
        environment="production",
        comparator=comparator,
        threshold=threshold,
        enabled=enabled,
        created_by=owner,
    )


@pytest.mark.django_db
class TestAlertEvaluation:
    def test_new_rule_state_is_exposed_without_running_evaluation(self) -> None:
        owner, project = _owner_project("state-api")
        rule = _rule(owner=owner, project=project)
        client = APIClient()
        client.force_authenticate(user=owner)

        response = client.get(f"/api/v1/projects/{project.id}/alert-rules/{rule.id}/")

        assert response.status_code == 200
        assert response.json()["state"]["status"] == "pending"
        assert response.json()["state"]["evaluated_at"] is None

    def test_new_disabled_rule_starts_disabled(self) -> None:
        owner, project = _owner_project("state-disabled")
        rule = _rule(owner=owner, project=project, enabled=False)

        state = AlertRuleState.objects.get(rule=rule)

        assert state.status == AlertRuleState.Status.DISABLED
        assert state.evaluated_at is None

    def test_evaluation_uses_persisted_tenant_and_exact_rule_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("scope")
        rule = _rule(
            owner=owner,
            project=project,
            time_range=AlertRule.TimeRange.SIX_HOURS,
        )
        evaluation_time = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
        source_timestamp = evaluation_time - timedelta(minutes=2)
        captured: dict[str, Any] = {}

        def fake_latest(**kwargs: Any) -> LatestNumericMetricPoint:
            captured.update(kwargs)
            return LatestNumericMetricPoint(timestamp=source_timestamp, value=12.5)

        monkeypatch.setattr(evaluation, "query_latest_numeric_metric_point", fake_latest)

        result = evaluation.evaluate_alert_rule(
            rule_id=rule.id,
            evaluated_at=evaluation_time,
        )

        assert result.status == AlertRuleState.Status.FIRING
        assert captured["organization_id"] == project.organization_id
        assert captured["project_id"] == project.id
        assert captured["metric_name"] == rule.metric_name
        assert captured["start"] == evaluation_time - timedelta(hours=6)
        assert captured["end"] == evaluation_time
        assert captured["service_name"] == "api"
        assert captured["environment"] == "production"
        state = AlertRuleState.objects.get(rule=rule)
        assert state.source_timestamp == source_timestamp
        assert state.state_changed_at == evaluation_time

    @pytest.mark.parametrize(
        ("comparator", "value", "threshold", "expected"),
        [
            (AlertRule.Comparator.GREATER_THAN, 10.0, 10.0, AlertRuleState.Status.OK),
            (
                AlertRule.Comparator.GREATER_THAN_OR_EQUAL,
                10.0,
                10.0,
                AlertRuleState.Status.FIRING,
            ),
            (AlertRule.Comparator.LESS_THAN, 9.0, 10.0, AlertRuleState.Status.FIRING),
            (
                AlertRule.Comparator.LESS_THAN_OR_EQUAL,
                10.0,
                10.0,
                AlertRuleState.Status.FIRING,
            ),
        ],
    )
    def test_comparator_semantics_are_explicit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        comparator: str,
        value: float,
        threshold: float,
        expected: str,
    ) -> None:
        owner, project = _owner_project(f"compare-{comparator}")
        rule = _rule(
            owner=owner,
            project=project,
            comparator=comparator,
            threshold=threshold,
        )
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: LatestNumericMetricPoint(
                timestamp=datetime(2026, 10, 11, 8, 59, tzinfo=UTC),
                value=value,
            ),
        )

        result = evaluation.evaluate_alert_rule(
            rule_id=rule.id,
            evaluated_at=datetime(2026, 10, 11, 9, 0, tzinfo=UTC),
        )

        assert result.status == expected

    def test_no_data_is_distinct_from_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner, project = _owner_project("no-data")
        rule = _rule(owner=owner, project=project)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: None,
        )

        result = evaluation.evaluate_alert_rule(rule_id=rule.id)

        assert result.status == AlertRuleState.Status.NO_DATA
        state = AlertRuleState.objects.get(rule=rule)
        assert state.error_code == ""
        assert state.source_timestamp is None

    @pytest.mark.parametrize(
        ("failure", "expected_code"),
        [
            (RuntimeError("clickhouse unavailable"), evaluation.TELEMETRY_QUERY_ERROR),
            (
                AmbiguousLatestMetricPoint("ambiguous"),
                evaluation.AMBIGUOUS_POINT_ERROR,
            ),
        ],
    )
    def test_query_failures_are_error_not_no_data(
        self,
        monkeypatch: pytest.MonkeyPatch,
        failure: Exception,
        expected_code: str,
    ) -> None:
        owner, project = _owner_project(f"failure-{expected_code}")
        rule = _rule(owner=owner, project=project)

        def fail(**_kwargs: Any) -> None:
            raise failure

        monkeypatch.setattr(evaluation, "query_latest_numeric_metric_point", fail)

        result = evaluation.evaluate_alert_rule(rule_id=rule.id)

        assert result.status == AlertRuleState.Status.ERROR
        assert result.error_code == expected_code
        assert AlertRuleState.objects.get(rule=rule).status == AlertRuleState.Status.ERROR

    def test_non_finite_observed_value_is_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner, project = _owner_project("non-finite")
        rule = _rule(owner=owner, project=project)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: LatestNumericMetricPoint(
                timestamp=datetime.now(UTC),
                value=float("nan"),
            ),
        )

        result = evaluation.evaluate_alert_rule(rule_id=rule.id)

        assert result.status == AlertRuleState.Status.ERROR
        assert result.error_code == evaluation.NON_FINITE_VALUE_ERROR

    def test_same_state_does_not_move_state_changed_at(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("stable-state")
        rule = _rule(owner=owner, project=project)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: LatestNumericMetricPoint(
                timestamp=datetime(2026, 10, 11, 8, 59, tzinfo=UTC),
                value=12.0,
            ),
        )
        first_time = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
        second_time = first_time + timedelta(minutes=1)

        evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=first_time)
        evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=second_time)

        state = AlertRuleState.objects.get(rule=rule)
        assert state.status == AlertRuleState.Status.FIRING
        assert state.evaluated_at == second_time
        assert state.state_changed_at == first_time

    def test_condition_change_invalidates_old_state_without_querying_clickhouse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("invalidate")
        rule = _rule(owner=owner, project=project)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: LatestNumericMetricPoint(
                timestamp=datetime.now(UTC),
                value=12.0,
            ),
        )
        evaluation.evaluate_alert_rule(rule_id=rule.id)
        assert AlertRuleState.objects.get(rule=rule).status == AlertRuleState.Status.FIRING

        updated = update_alert_rule(rule=rule, threshold=20.0)

        state = AlertRuleState.objects.get(rule=updated)
        assert state.status == AlertRuleState.Status.PENDING
        assert state.evaluated_at is None
        assert state.source_timestamp is None

        disabled = update_alert_rule(rule=updated, enabled=False)
        assert AlertRuleState.objects.get(rule=disabled).status == AlertRuleState.Status.DISABLED

    def test_stale_result_is_not_persisted_after_rule_changes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("stale")
        rule = _rule(owner=owner, project=project)

        def mutate_rule(**_kwargs: Any) -> LatestNumericMetricPoint:
            current = AlertRule.objects.get(pk=rule.pk)
            update_alert_rule(rule=current, threshold=999.0)
            return LatestNumericMetricPoint(timestamp=datetime.now(UTC), value=50.0)

        monkeypatch.setattr(evaluation, "query_latest_numeric_metric_point", mutate_rule)

        result = evaluation.evaluate_alert_rule(rule_id=rule.id)

        assert result.skipped is True
        state = AlertRuleState.objects.get(rule=rule)
        assert state.status == AlertRuleState.Status.PENDING
        assert state.evaluated_at is None

    def test_older_overlapping_evaluation_cannot_overwrite_newer_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("evaluation-order")
        rule = _rule(owner=owner, project=project)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: LatestNumericMetricPoint(
                timestamp=datetime(2026, 10, 11, 8, 59, tzinfo=UTC),
                value=12.0,
            ),
        )
        newer_time = datetime(2026, 10, 11, 9, 5, tzinfo=UTC)
        older_time = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)

        newer = evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=newer_time)
        older = evaluation.evaluate_alert_rule(rule_id=rule.id, evaluated_at=older_time)

        assert newer.skipped is False
        assert older.skipped is True
        state = AlertRuleState.objects.get(rule=rule)
        assert state.evaluated_at == newer_time
        assert state.status == AlertRuleState.Status.FIRING

    def test_management_command_scopes_to_one_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner_a, project_a = _owner_project("command-scope-a")
        rule_a = _rule(owner=owner_a, project=project_a)
        owner_b, project_b = _owner_project("command-scope-b")
        rule_b = _rule(owner=owner_b, project=project_b)
        monkeypatch.setattr(
            evaluation,
            "query_latest_numeric_metric_point",
            lambda **_kwargs: None,
        )
        output = StringIO()

        call_command("evaluate_alerts", project_id=project_a.id, stdout=output)

        assert AlertRuleState.objects.get(rule=rule_a).status == AlertRuleState.Status.NO_DATA
        assert AlertRuleState.objects.get(rule=rule_b).status == AlertRuleState.Status.PENDING
        assert "evaluated=1" in output.getvalue()

    def test_management_command_reports_evaluation_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner, project = _owner_project("command-error")
        _rule(owner=owner, project=project)

        def fail(**_kwargs: Any) -> None:
            raise RuntimeError("clickhouse unavailable")

        monkeypatch.setattr(evaluation, "query_latest_numeric_metric_point", fail)
        output = StringIO()

        with pytest.raises(CommandError, match="1 alert rule"):
            call_command("evaluate_alerts", project_id=project.id, stdout=output)

        assert "error=1" in output.getvalue()


class FakeQueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.closed = False
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, sql: str, *, parameters: dict[str, Any]) -> FakeQueryResult:
        self.calls.append((sql, parameters))
        return FakeQueryResult(self.rows)

    def close(self) -> None:
        self.closed = True


def test_latest_metric_query_is_tenant_scoped_and_detects_timestamp_ties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    project_id = uuid4()
    at = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
    client = FakeClickHouseClient([(at, 11.0)])
    monkeypatch.setattr(metrics_query, "get_clickhouse_client", lambda: client)

    point = metrics_query.query_latest_numeric_metric_point(
        organization_id=organization_id,
        project_id=project_id,
        metric_name="queue.depth",
        start=at - timedelta(hours=1),
        end=at + timedelta(seconds=1),
        service_name="worker",
        environment="production",
    )

    assert point == LatestNumericMetricPoint(timestamp=at, value=11.0)
    sql, parameters = client.calls[0]
    assert "organization_id = {organization_id:UUID}" in sql
    assert "project_id = {project_id:UUID}" in sql
    assert "number_value IS NOT NULL" in sql
    assert "ORDER BY timestamp DESC LIMIT 2" in sql
    assert parameters["organization_id"] == organization_id
    assert parameters["project_id"] == project_id
    assert parameters["service_name"] == "worker"
    assert parameters["environment"] == "production"
    assert client.closed

    tied_client = FakeClickHouseClient([(at, 11.0), (at, 12.0)])
    monkeypatch.setattr(metrics_query, "get_clickhouse_client", lambda: tied_client)
    with pytest.raises(AmbiguousLatestMetricPoint):
        metrics_query.query_latest_numeric_metric_point(
            organization_id=organization_id,
            project_id=project_id,
            metric_name="queue.depth",
            start=at - timedelta(hours=1),
            end=at + timedelta(seconds=1),
        )
