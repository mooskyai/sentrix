"""Opt-in demo data for the implemented Sentrix V1 M1–M6.2 features.

Runs entirely inside the Django process but posts binary OTLP to Sentrix's
normal authenticated ingest views, so the usual tenant and sink paths apply.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.logs.v1.logs_pb2 import SeverityNumber
from rest_framework.test import APIClient

from apps.alerts.evaluation import evaluate_enabled_alert_rules
from apps.alerts.models import AlertRule, AlertRuleState, NotificationChannel
from apps.alerts.notification_channels import create_notification_channel
from apps.alerts.services import create_alert_rule
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectApiKey, ProjectDashboardPanel
from apps.projects.services import create_project_api_key, create_project_dashboard_panel
from apps.telemetry.clickhouse_schema import get_clickhouse_client, validate_clickhouse_schema
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE

DEMO_SCOPE = "sentrix.demo.seed"
DEMO_CHANNEL = "Demo webhook (disabled)"

# A second authorized organization intentionally repeats the checkout identity.
# This tests browser project/organization switching, not foreign-user authorization.
PRIMARY = (
    ("demo-api", "production", (("demo.http.requests", 200.0), ("demo.http.latency_ms", 35.0))),
    (
        "demo-checkout",
        "production",
        (("demo.http.requests", 120.0), ("demo.checkout.failures", 12.0)),
    ),
    (
        "demo-payments",
        "production",
        (("demo.http.latency_ms", 140.0), ("demo.payment.failures", 1.0)),
    ),
    ("demo-checkout", "staging", (("demo.http.requests", 25.0), ("demo.checkout.failures", 2.0))),
    ("demo-worker", "", (("demo.queue.depth", 42.0),)),
    ("demo-batch", "production", (("demo.jobs.completed", 15.0),)),
    ("demo-archive", "production", (("demo.jobs.completed", 100.0),)),
)
SECONDARY = (
    (
        "demo-checkout",
        "production",
        (("demo.http.requests", 30.0), ("demo.checkout.failures", 0.0)),
    ),
    ("demo-worker", "staging", (("demo.queue.depth", 3.0),)),
)


def _attribute(target: Any, key: str, value: str) -> None:
    item = target.attributes.add()
    item.key = key
    item.value.string_value = value


def _resource(target: Any, service: str, environment: str, run_id: str) -> None:
    _attribute(target, "service.name", service)
    _attribute(target, "deployment.environment.name", environment)
    _attribute(target, DEMO_SCOPE, run_id)


def demo_payloads(*, secondary: bool, anchor_ns: int, run_id: str) -> tuple[dict[str, bytes], str]:
    """Build realistic, bounded OTLP protobuf messages with one correlated trace."""
    services = SECONDARY if secondary else PRIMARY
    metrics = ExportMetricsServiceRequest()
    logs = ExportLogsServiceRequest()
    traces = ExportTraceServiceRequest()
    trace_id = uuid4().hex
    root_id, child_id, final_id = (uuid4().bytes[:8] for _ in range(3))

    for position, (service, environment, metric_values) in enumerate(services):
        age_minutes = {"demo-batch": 180, "demo-archive": 2160}.get(service, 0)
        resource_metric = metrics.resource_metrics.add()
        _resource(resource_metric.resource, service, environment, run_id)
        scope_metrics = resource_metric.scope_metrics.add()
        scope_metrics.scope.name = "sentrix.demo"
        for metric_name, latest in metric_values:
            metric = scope_metrics.metrics.add()
            metric.name = metric_name
            metric.description = "Synthetic Sentrix demo observation"
            metric.unit = "ms" if metric_name.endswith("latency_ms") else "1"
            for offset_minutes, value in ((12, latest * 0.8), (2, latest)):
                point = metric.gauge.data_points.add()
                point.time_unix_nano = (
                    anchor_ns - (age_minutes + offset_minutes) * 60 * 1_000_000_000
                )
                point.as_double = value
                _attribute(point, DEMO_SCOPE, run_id)

        resource_logs = logs.resource_logs.add()
        _resource(resource_logs.resource, service, environment, run_id)
        scope_logs = resource_logs.scope_logs.add()
        scope_logs.scope.name = "sentrix.demo"
        record = scope_logs.log_records.add()
        record.time_unix_nano = anchor_ns - (age_minutes * 60 + 60 + position) * 1_000_000_000
        record.observed_time_unix_nano = record.time_unix_nano
        is_error = service == "demo-checkout" and environment == "production" and not secondary
        record.severity_number = (
            SeverityNumber.SEVERITY_NUMBER_ERROR
            if is_error
            else SeverityNumber.SEVERITY_NUMBER_INFO
        )
        record.severity_text = "ERROR" if is_error else "INFO"
        record.body.string_value = (
            "Demo checkout payment retry (synthetic)" if is_error else f"Demo {service} observed"
        )
        _attribute(record, DEMO_SCOPE, run_id)
        if is_error:
            record.trace_id = bytes.fromhex(trace_id)
            record.span_id = child_id

    # One trace with observed cross-service parentage, usable by the M4 trace viewer.
    # This is only fixture data; the M6.4 map is not implemented yet.
    trace_services = (
        (("demo-checkout", "production"),)
        if secondary
        else (
            ("demo-api", "production"),
            ("demo-checkout", "production"),
            ("demo-payments", "production"),
        )
    )
    for index, (service, environment) in enumerate(trace_services):
        resource_spans = traces.resource_spans.add()
        _resource(resource_spans.resource, service, environment, run_id)
        scope_spans = resource_spans.scope_spans.add()
        scope_spans.scope.name = "sentrix.demo"
        span = scope_spans.spans.add()
        span.trace_id = bytes.fromhex(trace_id)
        span.span_id = (root_id, child_id, final_id)[index]
        if index > 0:
            span.parent_span_id = (root_id, child_id)[index - 1]
        span.name = ("HTTP GET /shop", "checkout.submit", "payments.authorize")[index]
        span.start_time_unix_nano = anchor_ns - 45 * 1_000_000_000 + index * 5_000_000
        span.end_time_unix_nano = span.start_time_unix_nano + 30_000_000
        _attribute(span, DEMO_SCOPE, run_id)

    return {
        "metrics": metrics.SerializeToString(),
        "logs": logs.SerializeToString(),
        "traces": traces.SerializeToString(),
    }, trace_id


def _owned_org(user: User, suffix: str) -> Organization:
    slug = f"sentrix-demo-u{user.pk}-{suffix}"
    name = f"Sentrix Demo {suffix.title()} (user {user.pk})"
    organization, created = Organization.objects.get_or_create(slug=slug, defaults={"name": name})
    if not created:
        if organization.name != name:
            raise CommandError(f"Reserved demo organization slug {slug} is already in use.")
        if not OrganizationMembership.objects.filter(
            organization=organization, user=user, role=OrganizationMembership.Role.OWNER
        ).exists():
            raise CommandError(
                f"Refusing to modify demo organization {slug} without owner membership."
            )
    else:
        OrganizationMembership.objects.create(
            organization=organization, user=user, role=OrganizationMembership.Role.OWNER
        )
    return organization


def _owned_project(user: User, organization: Organization, slug: str) -> Project:
    name = "Online Store (synthetic)" if slug == "online-store" else "Isolated Store (synthetic)"
    project, created = Project.objects.get_or_create(
        organization=organization,
        slug=slug,
        defaults={"name": name, "created_by": user},
    )
    if not created and (project.name != name or project.created_by_id != user.pk):
        raise CommandError(f"Refusing to overwrite non-demo project {organization.slug}/{slug}.")
    return project


def _ensure_panel(
    user: User, project: Project, title: str, metric: str, service: str, env: str
) -> None:
    if ProjectDashboardPanel.objects.filter(
        project=project, metric_name=metric, time_range="1h", service_name=service, environment=env
    ).exists():
        return
    create_project_dashboard_panel(
        project=project,
        title=title,
        metric_name=metric,
        time_range="1h",
        service_name=service,
        environment=env,
        created_by=user,
    )


def _ensure_alert(
    user: User,
    project: Project,
    name: str,
    metric: str,
    service: str,
    env: str,
    threshold: float,
    *,
    enabled: bool = True,
) -> None:
    existing = AlertRule.objects.filter(project=project, name=name).first()
    if existing:
        if (
            existing.metric_name != metric
            or existing.service_name != service
            or existing.environment != env
            or existing.time_range != "1h"
            or existing.comparator != "gt"
            or existing.threshold != threshold
            or existing.enabled != enabled
        ):
            raise CommandError(f"Existing demo rule {name} was modified; refusing to overwrite it.")
        return
    create_alert_rule(
        project=project,
        name=name,
        metric_name=metric,
        time_range="1h",
        service_name=service,
        environment=env,
        comparator="gt",
        threshold=threshold,
        enabled=enabled,
        created_by=user,
    )


def _control_plane(user: User) -> tuple[Project, Project]:
    with transaction.atomic():
        primary = _owned_project(user, _owned_org(user, "primary"), "online-store")
        secondary = _owned_project(user, _owned_org(user, "secondary"), "isolated-store")
        _ensure_panel(
            user, primary, "Incoming demo requests", "demo.http.requests", "demo-api", "production"
        )
        _ensure_panel(
            user,
            primary,
            "Checkout failures",
            "demo.checkout.failures",
            "demo-checkout",
            "production",
        )
        _ensure_panel(user, primary, "Worker queue depth", "demo.queue.depth", "demo-worker", "")
        _ensure_panel(
            user,
            secondary,
            "Isolated checkout requests",
            "demo.http.requests",
            "demo-checkout",
            "production",
        )
        _ensure_alert(
            user,
            primary,
            "Demo checkout failures",
            "demo.checkout.failures",
            "demo-checkout",
            "production",
            5.0,
        )
        _ensure_alert(
            user, primary, "Demo worker backlog", "demo.queue.depth", "demo-worker", "", 60.0
        )
        _ensure_alert(
            user,
            primary,
            "Demo disabled alert",
            "demo.queue.depth",
            "demo-worker",
            "",
            30.0,
            enabled=False,
        )
        if not ProjectApiKey.objects.filter(
            project=primary, name="Demo exporter (revoked)"
        ).exists():
            demo_key, _unused_token = create_project_api_key(
                project=primary, name="Demo exporter (revoked)", created_by=user
            )
            demo_key.revoked_at = timezone.now()
            demo_key.save(update_fields=["revoked_at", "updated_at"])
        if NotificationChannel.objects.filter(project=primary, enabled=True).exists():
            raise CommandError("Disable all demo-project notification channels before seeding.")
        if not NotificationChannel.objects.filter(project=primary, name=DEMO_CHANNEL).exists():
            create_notification_channel(
                project=primary,
                name=DEMO_CHANNEL,
                endpoint_url="https://localhost/sentrix-demo-disabled",
                enabled=False,
                created_by=user,
            )
    return primary, secondary


def _ingest(project: Project, user: User, payloads: dict[str, bytes]) -> None:
    key, token = create_project_api_key(
        project=project, name="Temporary demo seed key", created_by=user
    )
    try:
        api = APIClient(HTTP_HOST="localhost")
        for signal in ("metrics", "logs", "traces"):
            response = api.post(
                f"/v1/{signal}",
                data=payloads[signal],
                content_type=OTLP_PROTOBUF_CONTENT_TYPE,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            if response.status_code != 200:
                raise CommandError(
                    f"Demo OTLP {signal} ingestion failed (HTTP {response.status_code})."
                )
    finally:
        # The plaintext key is never displayed or retained. Even on failure, delete it.
        key.delete()


def _verify(user: User, project: Project, expected_services: set[tuple[str, str]]) -> None:
    api = APIClient(HTTP_HOST="localhost")
    api.force_authenticate(user=user)
    end = datetime.now(UTC)
    result = api.get(
        f"/api/v1/projects/{project.pk}/services/catalog/",
        {"start": (end - timedelta(days=7)).isoformat(), "end": end.isoformat(), "limit": "500"},
    )
    if result.status_code != 200:
        raise CommandError(f"Demo catalog read failed (HTTP {result.status_code}).")
    observed = {(item["service_name"], item["environment"]) for item in result.json()["services"]}
    if not expected_services.issubset(observed):
        raise CommandError("Demo catalog did not contain every expected exact service identity.")


class Command(BaseCommand):
    help = "Seed synthetic M1–M6.2 demo organizations, projects, alerts and OTLP telemetry."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--username",
            required=True,
            help="Existing login to own the demo organizations; no password is created.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        username = str(options["username"])
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError("Active Sentrix user not found; use an existing account.") from exc

        # Do not create even demo control-plane records if telemetry storage is unavailable.
        try:
            client = get_clickhouse_client()
            try:
                schema_errors = validate_clickhouse_schema(client)
            finally:
                client.close()
        except Exception as exc:
            raise CommandError(
                "ClickHouse schema check failed; check the API/ClickHouse services."
            ) from exc
        if schema_errors:
            raise CommandError("ClickHouse schema is not ready; run manage.py clickhouse_schema.")

        primary, secondary = _control_plane(user)
        run_id = uuid4().hex
        anchor_ns = time.time_ns() - 10_000_000_000
        for project, is_secondary in ((primary, False), (secondary, True)):
            payloads, trace_id = demo_payloads(
                secondary=is_secondary, anchor_ns=anchor_ns, run_id=run_id
            )
            _ingest(project, user, payloads)
            expected = SECONDARY if is_secondary else PRIMARY
            _verify(user, project, {(service, environment) for service, environment, _ in expected})
            self.stdout.write(
                f"Demo project: {project.organization.slug}/{project.slug} "
                f"(project_id={project.pk}, trace_id={trace_id})"
            )
        # Evaluate only this demo project's rules against its freshly ingested metrics.
        # The only demo channel is disabled, so no webhook deliveries are generated.
        results = evaluate_enabled_alert_rules(project_id=primary.id)
        if any(result.status == AlertRuleState.Status.ERROR for result in results):
            raise CommandError("Demo alert evaluation failed; inspect ClickHouse and alert rules.")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo seed finished. Sign in with the existing user and open Services, Metrics, "
                "Logs, Traces, Dashboards and Alerts. All observations are synthetic. "
                "Re-running appends telemetry; it does not delete data or send webhooks."
            )
        )
