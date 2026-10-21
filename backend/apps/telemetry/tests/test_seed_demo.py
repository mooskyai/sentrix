from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from rest_framework.test import APIClient

from apps.alerts.models import AlertRule, AlertRuleState, NotificationChannel
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectApiKey, ProjectDashboardPanel
from apps.telemetry.management.commands import seed_demo


def _dimensions(message: Any) -> tuple[str, str]:
    values = {item.key: item.value.string_value for item in message.attributes}
    return values["service.name"], values["deployment.environment.name"]


def test_payloads_include_exact_environment_counts_errors_and_correlated_spans() -> None:
    anchor = 1_780_000_000_000_000_000
    payloads, trace_id = seed_demo.demo_payloads(
        secondary=False, anchor_ns=anchor, run_id="fixture-run"
    )
    metrics = ExportMetricsServiceRequest.FromString(payloads["metrics"])
    logs = ExportLogsServiceRequest.FromString(payloads["logs"])
    traces = ExportTraceServiceRequest.FromString(payloads["traces"])

    identities = {_dimensions(item.resource) for item in metrics.resource_metrics}
    assert ("demo-checkout", "production") in identities
    assert ("demo-checkout", "staging") in identities
    assert ("demo-worker", "") in identities
    assert len(identities) == len(seed_demo.PRIMARY)
    assert all(
        0 < point.time_unix_nano < anchor
        for item in metrics.resource_metrics
        for metric in item.scope_metrics[0].metrics
        for point in metric.gauge.data_points
    )

    errors = [
        record
        for item in logs.resource_logs
        for record in item.scope_logs[0].log_records
        if record.severity_number >= 17
    ]
    assert len(errors) == 1
    assert errors[0].trace_id.hex() == trace_id
    spans = [item.scope_spans[0].spans[0] for item in traces.resource_spans]
    assert len(spans) == 3
    assert spans[1].parent_span_id == spans[0].span_id
    assert spans[2].parent_span_id == spans[1].span_id
    assert all(span.trace_id.hex() == trace_id for span in spans)


def test_secondary_reuses_exact_identity_without_production_failure_log() -> None:
    payloads, _trace_id = seed_demo.demo_payloads(
        secondary=True, anchor_ns=1_780_000_000_000_000_000, run_id="other-run"
    )
    metrics = ExportMetricsServiceRequest.FromString(payloads["metrics"])
    logs = ExportLogsServiceRequest.FromString(payloads["logs"])
    assert ("demo-checkout", "production") in {
        _dimensions(item.resource) for item in metrics.resource_metrics
    }
    assert all(
        record.severity_number < 17
        for item in logs.resource_logs
        for record in item.scope_logs[0].log_records
    )


@pytest.mark.django_db
def test_unknown_login_fails_without_creating_demo_data() -> None:
    with pytest.raises(CommandError, match="Active Sentrix user not found"):
        call_command("seed_demo", username="does-not-exist")
    assert not Organization.objects.filter(slug__startswith="sentrix-demo-").exists()


@pytest.mark.django_db
def test_command_reuses_control_plane_and_never_enables_webhook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User.objects.create_user(username=f"demo-{uuid4().hex[:12]}")

    class FakeClient:
        closed = False

        def close(self) -> None:
            self.closed = True

    ch = FakeClient()
    monkeypatch.setattr(seed_demo, "get_clickhouse_client", lambda: ch)
    monkeypatch.setattr(seed_demo, "validate_clickhouse_schema", lambda _client: [])
    ingested: list[str] = []
    monkeypatch.setattr(
        seed_demo, "_ingest", lambda project, _user, _payloads: ingested.append(project.slug)
    )
    monkeypatch.setattr(seed_demo, "_verify", lambda _user, _project, _expected: None)
    monkeypatch.setattr(seed_demo, "evaluate_enabled_alert_rules", lambda **_kwargs: [])

    for _ in range(2):
        call_command("seed_demo", username=user.username, stdout=StringIO())
    assert ch.closed
    assert ingested == ["online-store", "isolated-store"] * 2
    projects = Project.objects.filter(organization__slug__startswith=f"sentrix-demo-u{user.pk}-")
    assert projects.count() == 2
    assert ProjectDashboardPanel.objects.filter(project__in=projects).count() == 4
    assert AlertRule.objects.filter(project__in=projects).count() == 3
    assert AlertRuleState.objects.filter(rule__project__in=projects, status="pending").count() == 2
    assert AlertRuleState.objects.filter(rule__project__in=projects, status="disabled").count() == 1
    assert NotificationChannel.objects.filter(project__in=projects, enabled=False).count() == 1
    assert not NotificationChannel.objects.filter(project__in=projects, enabled=True).exists()
    assert ProjectApiKey.objects.filter(project__in=projects, revoked_at__isnull=False).count() == 1


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_live_seed_uses_otlp_and_isolated_project_queries() -> None:
    user = User.objects.create_user(username=f"seed-live-{uuid4().hex[:12]}")
    call_command("seed_demo", username=user.username, stdout=StringIO())
    primary = Project.objects.get(organization__slug=f"sentrix-demo-u{user.pk}-primary")
    secondary = Project.objects.get(organization__slug=f"sentrix-demo-u{user.pk}-secondary")
    browser = APIClient(HTTP_HOST="localhost")
    browser.force_authenticate(user=user)

    first = browser.get(f"/api/v1/projects/{primary.id}/services/catalog/")
    second = browser.get(f"/api/v1/projects/{secondary.id}/services/catalog/")
    assert first.status_code == second.status_code == 200
    assert len(first.json()["services"]) == len(seed_demo.PRIMARY) - 1  # 36h archive is out.
    assert len(second.json()["services"]) == len(seed_demo.SECONDARY)
    end = datetime.now(UTC)
    week = browser.get(
        f"/api/v1/projects/{primary.id}/services/catalog/",
        {"start": (end - timedelta(days=7)).isoformat(), "end": end.isoformat()},
    )
    assert week.status_code == 200
    assert len(week.json()["services"]) == len(seed_demo.PRIMARY)
    detail = browser.get(
        f"/api/v1/projects/{primary.id}/services/detail/",
        {"service_name": "demo-checkout", "environment": "production"},
    )
    assert detail.status_code == 200
    assert any(
        metric["name"] == "demo.checkout.failures" for metric in detail.json()["metric_names"]
    )
    assert len(detail.json()["error_logs"]) == 1
    assert detail.json()["trace_references"]

    other = browser.get(
        f"/api/v1/projects/{secondary.id}/services/detail/",
        {"service_name": "demo-checkout", "environment": "production"},
    )
    assert other.status_code == 200
    assert other.json()["error_logs"] == []
    assert ProjectApiKey.objects.filter(project=primary, revoked_at__isnull=False).count() == 1
    assert (
        AlertRuleState.objects.filter(
            rule__project=primary, status=AlertRuleState.Status.FIRING
        ).count()
        == 1
    )
    assert (
        AlertRuleState.objects.filter(
            rule__project=primary, status=AlertRuleState.Status.OK
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_seeder_refuses_enabled_demo_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User.objects.create_user(username=f"seed-guard-{uuid4().hex[:12]}")

    class FakeClient:
        def close(self) -> None:
            return None

    monkeypatch.setattr(seed_demo, "get_clickhouse_client", FakeClient)
    monkeypatch.setattr(seed_demo, "validate_clickhouse_schema", lambda _client: [])
    monkeypatch.setattr(seed_demo, "_ingest", lambda *_args: None)
    monkeypatch.setattr(seed_demo, "_verify", lambda *_args: None)
    monkeypatch.setattr(seed_demo, "evaluate_enabled_alert_rules", lambda **_kwargs: [])
    call_command("seed_demo", username=user.username, stdout=StringIO())
    channel = NotificationChannel.objects.get(name=seed_demo.DEMO_CHANNEL)
    channel.enabled = True
    channel.save(update_fields=["enabled"])
    with pytest.raises(CommandError, match="Disable all demo-project notification channels"):
        call_command("seed_demo", username=user.username, stdout=StringIO())
