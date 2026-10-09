# Sentrix V1 M4 Testing — Logs and Trace Correlation

## 1. Testing principle

M4 testing must prove that correlation never bypasses tenant authorization. A trace ID, span ID, log
body, service name, or other telemetry field is searchable data only; none of those values may establish
organization/project authority.

## 2. M4.1 automated matrix

### LQ-001 — Viewer project read

A viewer membership receives HTTP 200 for its project's log search endpoint.

### LQ-002 — Foreign project non-discovery

A caller using an exact foreign project UUID receives `404`, and the ClickHouse client is never opened.

### LQ-003 — Tenant predicates

Every ClickHouse query includes authorized `organization_id` and `project_id` predicates derived from
the membership-scoped Django project.

### LQ-004 — Typed filter parameterization

Service, environment, minimum severity, body substring, timestamps, and trace ID remain ClickHouse
parameters. Tests include SQL-like body text and prove it is not interpolated into the SQL string.

### LQ-005 — Time and result bounds

Verify:

- timezone-aware RFC3339 timestamps are accepted;
- naive/invalid timestamps are rejected;
- `start >= end` is rejected;
- windows longer than seven days are rejected;
- omitted timestamps default to the previous hour;
- `limit` is restricted to `1..1000` and execution reads only `limit + 1` rows.

### LQ-006 — Severity and trace validation

`min_severity_number` accepts OpenTelemetry severity numbers `0..24`. Trace filters require exactly
32 hexadecimal characters and reject the all-zero identifier.

### LQ-007 — Raw response honesty

Rows preserve timestamps, severity/body, service/environment, scope/resource/log attributes, flags, and
correlation IDs. Stored all-zero trace/span sentinels become `null`; no correlation is invented.

### LQ-008 — Dependency failure

A ClickHouse failure returns HTTP `503`, does not leak dependency internals, and closes the client.

### LQ-009 — Live project isolation

Send the same uniquely identifiable log body and trace ID into two projects with two real project API
keys. Query through a session belonging to project A and prove only A's row is returned; querying project
B with that session returns `404`.

### LQ-010 — Regression gate

M4.1 keeps all M1-M3 backend/frontend/infrastructure checks green.

## 3. M4.1 focused checks

From the repository root with Compose available:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_logs_query_api.py -v
docker compose exec api /opt/venv/bin/ruff check apps/telemetry/logs_query.py apps/telemetry/logs_views.py apps/telemetry/tests/test_logs_query_api.py
docker compose exec api /opt/venv/bin/ruff format --check apps/telemetry/logs_query.py apps/telemetry/logs_views.py apps/telemetry/tests/test_logs_query_api.py
docker compose exec api /opt/venv/bin/mypy apps/telemetry/logs_query.py apps/telemetry/logs_views.py
```

Then run the complete release gate:

```powershell
./scripts/verify.ps1
```

## 4. Manual API smoke

With a real OTLP log already persisted for the project, authenticate through the normal browser/session
flow and query:

```text
GET /api/v1/projects/<project-uuid>/logs/search/
```

Use a narrow range containing the row. Verify exact service/environment filters, minimum severity,
case-insensitive `body_contains`, and exact trace ID where the log is correlated. Confirm an unmatched
filter returns a healthy empty result while ClickHouse unavailability returns a query error instead.

Do not validate isolation with an unscoped direct ClickHouse scan.

## 5. M4.1 stop condition

M4.1 is complete only after focused tests, the live project-isolation test, manual real-log API smoke,
and the full release gate pass; changes are committed and pushed; and:

```text
## main...origin/main
```

is clean. Only then may M4.2 Logs Explorer UI begin.
