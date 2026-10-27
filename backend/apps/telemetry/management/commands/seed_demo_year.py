"""Opt-in, resumable one-year synthetic history for reserved Sentrix demo projects.

Historical records are *not* evidence of a real framework SDK export.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from rest_framework.test import APIClient

from apps.organizations.models import OrganizationMembership
from apps.projects.models import Project
from apps.projects.services import create_project_api_key
from apps.telemetry.clickhouse_schema import get_clickhouse_client
from apps.telemetry.management.commands.seed_demo import DEMO_SCOPE, demo_payloads
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE

HISTORY_PREFIX = "sentrix-history-v1:"
SIGNAL_TABLES = {
    "metrics": "sentrix_metrics",
    "logs": "sentrix_logs",
    "traces": "sentrix_spans",
}
BATCH_DAYS = 7
MAX_DAYS = 365


def history_marker(day: date) -> str:
    return f"{HISTORY_PREFIX}{day.isoformat()}"


def history_payloads(
    *, project_id: UUID, day: date, anchor: datetime, secondary: bool
) -> dict[str, bytes]:
    """Build deterministic, correlated, explicitly synthetic OTLP records for one day."""
    if anchor.tzinfo is None or anchor.utcoffset() != timedelta(0):
        raise ValueError("History timestamps must be UTC aware.")
    payloads, _random_trace = demo_payloads(
        secondary=secondary,
        anchor_ns=int(anchor.timestamp() * 1_000_000_000),
        run_id=history_marker(day),
    )
    metrics = ExportMetricsServiceRequest.FromString(payloads["metrics"])
    logs = ExportLogsServiceRequest.FromString(payloads["logs"])
    traces = ExportTraceServiceRequest.FromString(payloads["traces"])

    # Distinct daily, repeatable values with a weekly rhythm; not copied production data.
    weekday_multiplier = 0.75 if day.weekday() >= 5 else 1.0
    seasonal_multiplier = 0.85 + (day.toordinal() % 31) / 100
    factor = weekday_multiplier * seasonal_multiplier
    for resource in metrics.resource_metrics:
        for scoped in resource.scope_metrics:
            for metric in scoped.metrics:
                for point in metric.gauge.data_points:
                    point.as_double *= factor

    identity = f"sentrix-synthetic:{project_id}:{day.isoformat()}"
    root_trace = uuid5(NAMESPACE_URL, f"{identity}:trace").bytes
    span_ids = [uuid5(NAMESPACE_URL, f"{identity}:span:{i}").bytes[:8] for i in range(3)]
    # The existing demo generator provides 1/3 correlated services plus a separate
    # synthetic Node-shaped span. Preserve those edges while making reruns stable.
    for index, resource in enumerate(traces.resource_spans):
        for scoped in resource.scope_spans:
            for span in scoped.spans:
                if not secondary and index == 3:
                    span.trace_id = uuid5(NAMESPACE_URL, f"{identity}:synthetic-node").bytes
                    span.span_id = uuid5(NAMESPACE_URL, f"{identity}:node-span").bytes[:8]
                    span.ClearField("parent_span_id")
                else:
                    span.trace_id = root_trace
                    span.span_id = span_ids[index]
                    if index:
                        span.parent_span_id = span_ids[index - 1]
                    else:
                        span.ClearField("parent_span_id")
    for resource in logs.resource_logs:
        for scoped in resource.scope_logs:
            for record in scoped.log_records:
                if record.trace_id:
                    record.trace_id = root_trace
                    record.span_id = span_ids[1]

    return {
        "metrics": cast(bytes, metrics.SerializeToString()),
        "logs": cast(bytes, logs.SerializeToString()),
        "traces": cast(bytes, traces.SerializeToString()),
    }


def observed_markers(project: Project) -> dict[str, set[str]]:
    """Check marker presence separately for all signals so partial retries can resume."""
    client = get_clickhouse_client()
    try:
        result: dict[str, set[str]] = {}
        for signal, table in SIGNAL_TABLES.items():
            time_column = "start_time" if signal == "traces" else "timestamp"
            # Names are constants above, never caller-controlled SQL fragments.
            sql = (
                f"SELECT DISTINCT resource_attributes['{DEMO_SCOPE}'] AS marker "
                f"FROM {table} WHERE "
                "organization_id = {organization_id:UUID} "
                "AND project_id = {project_id:UUID} "
                f"AND {time_column} >= {{oldest:DateTime64(9)}} "
                f"AND {time_column} < {{newest:DateTime64(9)}} "
                f"AND startsWith(resource_attributes['{DEMO_SCOPE}'], {{prefix:String}})"
            )
            # Two extra days for older demo-batch/archive samples near the boundary.
            now = datetime.now(UTC)
            rows = client.query(
                sql,
                parameters={
                    "organization_id": project.organization_id,
                    "project_id": project.id,
                    "oldest": now - timedelta(days=MAX_DAYS + 3),
                    "newest": now + timedelta(days=1),
                    "prefix": HISTORY_PREFIX,
                },
            ).result_rows
            result[signal] = {str(row[0]) for row in rows}
        return result
    finally:
        client.close()


def _extend_messages(destination: Any, incoming: Any, signal: str) -> None:
    field = {
        "metrics": "resource_metrics",
        "logs": "resource_logs",
        "traces": "resource_spans",
    }[signal]
    getattr(destination, field).extend(getattr(incoming, field))


def seed_history(
    project: Project, owner: User, *, days: int, now: datetime, secondary: bool
) -> tuple[int, int]:
    seen = observed_markers(project)
    expected = [history_marker((now - timedelta(days=offset)).date()) for offset in range(days)]
    # Oldest-to-newest makes a partial/interrupted run straightforward to inspect.
    offsets = list(reversed(range(days)))
    key = None
    inserted_days = 0
    inserted_requests = 0
    try:
        for start in range(0, len(offsets), BATCH_DAYS):
            chunk = offsets[start : start + BATCH_DAYS]
            requests: dict[str, Any] = {
                "metrics": ExportMetricsServiceRequest(),
                "logs": ExportLogsServiceRequest(),
                "traces": ExportTraceServiceRequest(),
            }
            pending: dict[str, list[str]] = {signal: [] for signal in SIGNAL_TABLES}
            for offset in chunk:
                anchor = now - timedelta(days=offset)
                marker = history_marker(anchor.date())
                missing = [signal for signal in SIGNAL_TABLES if marker not in seen[signal]]
                if not missing:
                    continue
                payloads = history_payloads(
                    project_id=project.id,
                    day=anchor.date(),
                    anchor=anchor,
                    secondary=secondary,
                )
                for signal in missing:
                    message_type = type(requests[signal])
                    message = message_type.FromString(payloads[signal])
                    _extend_messages(requests[signal], message, signal)
                    pending[signal].append(marker)
            if not any(pending.values()):
                continue
            if key is None:
                key, token = create_project_api_key(
                    project=project, name="Temporary year-demo seed key", created_by=owner
                )
            api = APIClient(HTTP_HOST="localhost")
            for signal in SIGNAL_TABLES:
                if not pending[signal]:
                    continue
                response = api.post(
                    f"/v1/{signal}",
                    data=cast(bytes, requests[signal].SerializeToString()),
                    content_type=OTLP_PROTOBUF_CONTENT_TYPE,
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )
                if response.status_code != 200:
                    raise CommandError(
                        f"Year demo ingestion for {signal} failed (HTTP {response.status_code}); "
                        "rerun after resolving the receiver failure."
                    )
                seen[signal].update(pending[signal])
                inserted_requests += 1
            inserted_days += len({m for markers in pending.values() for m in markers})
    finally:
        if key is not None:
            key.delete()  # Never retain or print an active demo key.

    persisted = observed_markers(project)
    for signal, persisted_markers in persisted.items():
        unpersisted = set(expected) - persisted_markers
        if unpersisted:
            raise CommandError(
                f"Historical {signal} persistence incomplete for {len(unpersisted)} days in "
                f"{project.organization.slug}/{project.slug}."
            )
    return inserted_days, inserted_requests


@transaction.atomic
def create_nonmember(*, owner: User, username: str) -> User:
    """Make an auth-isolation fixture, never granting membership or a login secret."""
    if not username or len(username) > 150 or username == owner.username:
        raise CommandError("Use a distinct, nonempty foreign username (maximum 150 characters).")
    user, created = User.objects.get_or_create(
        username=username, defaults={"is_active": True, "is_staff": False, "is_superuser": False}
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    if (
        not user.is_active
        or user.is_staff
        or user.is_superuser
        or OrganizationMembership.objects.filter(user=user).exists()
    ):
        raise CommandError("Foreign user must be active, nonprivileged, and have zero memberships.")
    return user


class Command(BaseCommand):
    help = "Seed up to 365 days of bounded, resumable OTLP history in reserved demo projects."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--username", required=True, help="Existing demo owner login")
        parser.add_argument("--days", type=int, default=365, help="History days, 1 through 365")
        parser.add_argument(
            "--create-nonmember",
            action="store_true",
            help="Provision a safe, nonmember auth fixture",
        )
        parser.add_argument(
            "--nonmember-username", default="m732-nonmember", help="Nonmember fixture username"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = int(options["days"])
        if not 1 <= days <= MAX_DAYS:
            raise CommandError("--days must be between 1 and 365.")
        try:
            owner = User.objects.get(username=options["username"], is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError("An active existing owner account is required.") from exc
        if options["create_nonmember"]:
            username = str(options["nonmember_username"])
            # Validate before any expensive/demo writes. Membership is checked again later.
            if (
                not username
                or len(username) > 150
                or username == owner.username
                or OrganizationMembership.objects.filter(user__username=username).exists()
            ):
                raise CommandError(
                    "Nonmember username is invalid or already belongs to an organization."
                )
        # Reuse the established safe control-plane creation, schema check, recent
        # demo rows, disabled notifications, and alert evaluation.
        call_command("seed_demo", username=owner.username, stdout=self.stdout)
        now = datetime.now(UTC) - timedelta(minutes=10)
        for suffix, project_slug, secondary in (
            ("primary", "online-store", False),
            ("secondary", "isolated-store", True),
        ):
            project = Project.objects.get(
                organization__slug=f"sentrix-demo-u{owner.pk}-{suffix}", slug=project_slug
            )
            days_written, requests = seed_history(
                project, owner, days=days, now=now, secondary=secondary
            )
            self.stdout.write(
                f"Historical demo project: {project.organization.slug}/{project.slug} "
                f"(project_id={project.id}, days_written={days_written}, otlp_requests={requests})"
            )
        if options["create_nonmember"]:
            foreign = create_nonmember(owner=owner, username=str(options["nonmember_username"]))
            self.stdout.write(
                f"Foreign test account: {foreign.username} (active, zero organization memberships; "
                "password unchanged on reuse)."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synthetic history verified for {days} days in both reserved projects. "
                "Re-runs skip already persisted signal/day markers. "
                "UI queries remain limited to their supported time windows. "
                "This does not prove a real SDK export or foreign-user HTTP 404."
            )
        )
