# Sentrix M7.3.2 synthetic demo acceptance: read-only, no secrets, no writes.
# Invoke from the Sentrix repository root:
#   & "$HOME\Downloads\sentrix-m732-synthetic-acceptance.ps1" -Username admin
[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$Username = 'admin'
)

$ErrorActionPreference = 'Stop'
$code = @'
import os
import sys
from datetime import UTC, datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth.models import User
from apps.organizations.models import OrganizationMembership
from apps.projects.models import Project
from apps.telemetry.clickhouse_schema import get_clickhouse_client

username = sys.argv[1]
user = User.objects.get(username=username, is_active=True)


def project_for(suffix: str, project_slug: str) -> Project:
    project = Project.objects.select_related("organization").get(
        organization__slug=f"sentrix-demo-u{user.pk}-{suffix}",
        slug=project_slug,
        created_by=user,
    )
    if not OrganizationMembership.objects.filter(
        organization=project.organization,
        user=user,
        role=OrganizationMembership.Role.OWNER,
    ).exists():
        raise RuntimeError("Required demo organization ownership is missing.")
    return project


primary = project_for("primary", "online-store")
secondary = project_for("secondary", "isolated-store")
end = datetime.now(UTC)
start = end - timedelta(hours=24)
service = "demo-node-express"
environment = "integration"

base = """
FROM {table}
WHERE organization_id = {{org:UUID}}
  AND project_id = {{project:UUID}}
  AND {time_column} >= {{start:DateTime64(9)}}
  AND {time_column} < {{end:DateTime64(9)}}
  AND service_name = {{service:String}}
  AND environment = {{environment:String}}
"""

settings = """
SETTINGS max_execution_time = 8,
         max_rows_to_read = 250000,
         read_overflow_mode = 'throw'
"""


def query(client, project: Project, table: str, time_column: str, select: str):
    # Table and time-column names originate from fixed code constants only.
    sql = f"SELECT {select} " + base.format(table=table, time_column=time_column) + settings
    params = {
        "org": project.organization_id,
        "project": project.id,
        "start": start,
        "end": end,
        "service": service,
        "environment": environment,
    }
    return client.query(sql, parameters=params).result_rows[0]


try:
    client = get_clickhouse_client()
    try:
        primary_metrics = query(
            client, primary, "sentrix_metrics", "timestamp",
            "countIf(metric_name = 'demo.node.http.requests'), "
            "countIf(metric_name = 'demo.node.http.duration_ms')",
        )
        primary_logs = query(
            client, primary, "sentrix_logs", "timestamp", "count()"
        )[0]
        primary_spans = query(
            client, primary, "sentrix_spans", "start_time",
            "countIf(span_name = 'demo.node.checkout' "
            "AND span_kind = 2 "
            "AND resource_attributes['sentrix.demo.synthetic'] = 'true' "
            "AND attributes['sentrix.demo.synthetic'] = 'true' "
            "AND attributes['http.route'] = '/checkout')",
        )[0]

        secondary_counts = (
            query(client, secondary, "sentrix_metrics", "timestamp", "count()")[0],
            query(client, secondary, "sentrix_logs", "timestamp", "count()")[0],
            query(client, secondary, "sentrix_spans", "start_time", "count()")[0],
        )
    finally:
        client.close()
except Exception as exc:
    print(f"Synthetic read-back FAILED: query/dependency error ({type(exc).__name__}).")
    raise SystemExit(2) from None

print("SYNTHETIC Sentrix M7.3.2 UI fixture check")
print(f"Primary demo project: {primary.id}")
print(f"Secondary demo project: {secondary.id}")
print(f"UTC window: {start.isoformat()} to {end.isoformat()}")
print(f"Synthetic service/environment: {service} / {environment}")
print(f"Primary request metrics: {primary_metrics[0]}")
print(f"Primary duration metrics: {primary_metrics[1]}")
print(f"Primary logs: {primary_logs}")
print(f"Primary marked HTTP SERVER spans: {primary_spans}")
print("Secondary counts (metrics, logs, spans):", secondary_counts)

if (
    primary_metrics[0] < 1
    or primary_metrics[1] < 1
    or primary_logs < 1
    or primary_spans < 1
    or any(count != 0 for count in secondary_counts)
):
    print("FAIL: synthetic fixture not complete or project isolation violated.")
    raise SystemExit(1)

print("PASS: synthetic demo telemetry exists and is isolated to the primary project.")
print("NOT REAL SDK PROOF: M7.3.2 Node SDK persistence acceptance remains open.")
'@

docker compose exec -T api /opt/venv/bin/python -c $code $Username
if ($LASTEXITCODE -ne 0) {
    throw "Synthetic acceptance read-back failed (exit code $LASTEXITCODE)."
}
