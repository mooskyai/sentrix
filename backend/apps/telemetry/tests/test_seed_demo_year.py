from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from io import StringIO
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project
from apps.telemetry.management.commands import seed_demo_year


def test_year_history_payloads_are_reproducible_and_correlated() -> None:
    project_id = uuid4()
    day = date(2026, 5, 17)
    anchor = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    first = seed_demo_year.history_payloads(
        project_id=project_id, day=day, anchor=anchor, secondary=False
    )
    second = seed_demo_year.history_payloads(
        project_id=project_id, day=day, anchor=anchor, secondary=False
    )
    assert first == second

    metrics = ExportMetricsServiceRequest.FromString(first["metrics"])
    logs = ExportLogsServiceRequest.FromString(first["logs"])
    traces = ExportTraceServiceRequest.FromString(first["traces"])
    expected_marker = seed_demo_year.history_marker(day)
    assert all(
        any(
            a.key == "sentrix.demo.seed" and a.value.string_value == expected_marker
            for a in group.resource.attributes
        )
        for group in metrics.resource_metrics
    )
    trace_spans = [g.scope_spans[0].spans[0] for g in traces.resource_spans]
    assert len(trace_spans) == 4
    assert trace_spans[1].parent_span_id == trace_spans[0].span_id
    assert trace_spans[2].parent_span_id == trace_spans[1].span_id
    assert len({span.trace_id for span in trace_spans[:3]}) == 1
    assert trace_spans[3].trace_id != trace_spans[0].trace_id
    error_logs = [
        record
        for group in logs.resource_logs
        for record in group.scope_logs[0].log_records
        if record.trace_id
    ]
    assert len(error_logs) == 1
    assert error_logs[0].trace_id == trace_spans[1].trace_id
    assert error_logs[0].span_id == trace_spans[1].span_id
    assert all(
        0 < point.time_unix_nano <= int(anchor.timestamp() * 1_000_000_000)
        for group in metrics.resource_metrics
        for scoped in group.scope_metrics
        for metric in scoped.metrics
        for point in metric.gauge.data_points
    )


def test_history_secondary_does_not_contain_primary_synthetic_node() -> None:
    day = date(2026, 5, 17)
    payloads = seed_demo_year.history_payloads(
        project_id=uuid4(),
        day=day,
        anchor=datetime(2026, 5, 17, tzinfo=UTC),
        secondary=True,
    )
    traces = ExportTraceServiceRequest.FromString(payloads["traces"])
    assert len(traces.resource_spans) == 1


def test_history_rejects_naive_anchor() -> None:
    with pytest.raises(ValueError, match="UTC aware"):
        seed_demo_year.history_payloads(
            project_id=uuid4(),
            day=date(2026, 5, 17),
            anchor=datetime(2026, 5, 17),
            secondary=True,
        )


@pytest.mark.django_db
def test_nonmember_is_idempotent_nonprivileged_and_has_no_usable_password() -> None:
    owner = User.objects.create_user(username=f"year-owner-{uuid4().hex[:10]}")
    username = f"year-outsider-{uuid4().hex[:10]}"
    foreign = seed_demo_year.create_nonmember(owner=owner, username=username)
    assert foreign.is_active
    assert not foreign.is_staff and not foreign.is_superuser
    assert not foreign.has_usable_password()
    assert not OrganizationMembership.objects.filter(user=foreign).exists()
    assert seed_demo_year.create_nonmember(owner=owner, username=username).pk == foreign.pk
    with pytest.raises(CommandError, match="distinct"):
        seed_demo_year.create_nonmember(owner=owner, username=owner.username)

    org = Organization.objects.create(name="foreign-fixture", slug=f"foreign-{uuid4().hex[:12]}")
    OrganizationMembership.objects.create(
        organization=org, user=foreign, role=OrganizationMembership.Role.VIEWER
    )
    with pytest.raises(CommandError, match="zero memberships"):
        seed_demo_year.create_nonmember(owner=owner, username=username)


def test_chunking_resumes_individual_signal_days_without_duplicate_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = datetime(2026, 10, 27, 3, 10, tzinfo=UTC)
    project = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        organization=SimpleNamespace(slug="reserved"),
        slug="online-store",
    )
    owner = SimpleNamespace(pk=123)
    existing = seed_demo_year.history_marker((today - timedelta(days=1)).date())
    updated: dict[str, set[str]] = {name: set() for name in seed_demo_year.SIGNAL_TABLES}
    updated["metrics"].add(existing)
    calls: list[tuple[str, int]] = []
    secrets: list[Any] = []

    def fake_seen(_project: Any) -> dict[str, set[str]]:
        return {signal: set(markers) for signal, markers in updated.items()}

    def fake_key(**_kwargs: Any) -> tuple[Any, str]:
        key = SimpleNamespace(delete=lambda: secrets.append("deleted"))
        return key, "local-test-token"

    class FakeAPI:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def post(self, endpoint: str, data: bytes, **_kwargs: Any) -> Any:
            signal = endpoint.removeprefix("/v1/")
            message_type: Any = {
                "metrics": cast(type[Any], ExportMetricsServiceRequest),
                "logs": cast(type[Any], ExportLogsServiceRequest),
                "traces": ExportTraceServiceRequest,
            }[signal]
            parsed = message_type.FromString(data)
            field = {
                "metrics": "resource_metrics",
                "logs": "resource_logs",
                "traces": "resource_spans",
            }[signal]
            markers = {
                attr.value.string_value
                for group in getattr(parsed, field)
                for attr in group.resource.attributes
                if attr.key == "sentrix.demo.seed"
            }
            assert markers.isdisjoint(updated[signal])
            updated[signal].update(markers)
            calls.append((signal, len(markers)))
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(seed_demo_year, "observed_markers", fake_seen)
    monkeypatch.setattr(seed_demo_year, "create_project_api_key", fake_key)
    monkeypatch.setattr(seed_demo_year, "APIClient", FakeAPI)
    assert seed_demo_year.seed_history(
        cast(Project, project), cast(User, owner), days=2, now=today, secondary=False
    ) == (2, 3)
    assert calls == [("metrics", 1), ("logs", 2), ("traces", 2)]
    assert secrets == ["deleted"]
    assert seed_demo_year.seed_history(
        cast(Project, project), cast(User, owner), days=2, now=today, secondary=False
    ) == (0, 0)
    assert len(calls) == 3


@pytest.mark.django_db
def test_day_count_is_bounded_before_control_plane_changes() -> None:
    owner = User.objects.create_user(username=f"year-invalid-{uuid4().hex[:10]}")
    for count in (0, -1, 366, 10000):
        with pytest.raises(CommandError, match="between 1 and 365"):
            call_command("seed_demo_year", username=owner.username, days=count)
    assert not Organization.objects.filter(slug__startswith=f"sentrix-demo-u{owner.pk}-").exists()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_year_history_live_2_days_isolated_and_repeatable() -> None:
    owner = User.objects.create_user(username=f"year-live-{uuid4().hex[:12]}")
    foreign_username = f"year-live-other-{uuid4().hex[:12]}"
    args = {
        "username": owner.username,
        "days": 2,
        "create_nonmember": True,
        "nonmember_username": foreign_username,
    }
    call_command("seed_demo_year", **args, stdout=StringIO())
    primary = Project.objects.get(organization__slug=f"sentrix-demo-u{owner.pk}-primary")
    secondary = Project.objects.get(organization__slug=f"sentrix-demo-u{owner.pk}-secondary")
    first_primary = seed_demo_year.observed_markers(primary)
    first_secondary = seed_demo_year.observed_markers(secondary)
    assert all(len(rows) == 2 for rows in first_primary.values())
    assert all(len(rows) == 2 for rows in first_secondary.values())
    call_command("seed_demo_year", **args, stdout=StringIO())
    assert seed_demo_year.observed_markers(primary) == first_primary
    assert seed_demo_year.observed_markers(secondary) == first_secondary
    outsider = User.objects.get(username=foreign_username)
    assert not outsider.has_usable_password()
    browser = APIClient(HTTP_HOST="localhost")
    browser.force_authenticate(user=outsider)
    assert browser.get(f"/api/v1/projects/{primary.pk}/services/catalog/").status_code == 404
    assert browser.get(f"/api/v1/projects/{secondary.pk}/services/catalog/").status_code == 404
