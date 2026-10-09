# Sentrix V1 M3 Testing — Metrics Explorer and First Dashboard Panels

## 1. Testing principle

M3 testing must prove telemetry reads are both semantically honest and tenant safe. A chart rendering is
not evidence of a correct query boundary; authorization, ClickHouse predicates, query bounds, failure
behavior, and real persisted telemetry must be verified independently.

## 2. M3.1 automated matrix

### MQ-001 — Viewer project read

Given a viewer membership, the metrics catalog endpoint returns HTTP 200 for that viewer's project.
Read-only RBAC does not block observability reads.

### MQ-002 — Foreign project non-discovery

Given a user from another organization and an exact foreign project UUID, catalog/series returns `404`
and the ClickHouse client is never opened.

### MQ-003 — Tenant predicates

Every application query includes authorized `organization_id` and `project_id` predicates. Tests assert
those parameter values come from the resolved Django project.

### MQ-004 — Query value parameterization

Metric name, timestamps, service name, and environment are typed ClickHouse parameters. Caller strings
must never be concatenated into SQL.

### MQ-005 — Time-window validation

Verify:

- timezone-aware RFC3339 timestamps are accepted;
- naive/invalid timestamps are rejected;
- `start >= end` is rejected;
- windows longer than seven days are rejected;
- omitted timestamps use the one-hour default.

### MQ-006 — Result bounds

Verify catalog limit `1..500` and series limit `1..5000`. Series requests read at most `limit + 1`
rows so the response can report truncation without an unbounded count query.

### MQ-007 — Metric-shape honesty

Catalog metadata may list gauge, sum, histogram, exponential-histogram, and summary types. The M3.1
series endpoint returns only rows with `number_value`; tests must not flatten histogram/summary state.

### MQ-008 — Dependency failure

A ClickHouse query failure returns HTTP `503`, does not leak dependency internals, and closes the client.

### MQ-009 — Live ClickHouse project isolation

Ingest the same uniquely named metric into two projects using two real project API keys. Query through a
session belonging to project A and prove only project A's value is returned. Querying project B with the
same session must return `404`.

### MQ-010 — Regression gate

M3.1 must keep all M2 tests and quality checks green.

## 3. M3.1 release gate

Run from the repository root with the Compose stack available:

```powershell
./scripts/verify.ps1
```

The expected gate remains:

```text
Backend
  pytest
  ruff check
  ruff format --check
  mypy
  Django system check
  makemigrations --check --dry-run
  ClickHouse schema --check

Frontend
  lint
  typecheck
  tests
  production build

Repository
  docker compose config --quiet
  git diff --check
```

After the gate:

```powershell
git status --short
git diff --stat
git diff --check
```

Do not commit M3.1 if any check is red.

## 4. Manual API smoke

After sending real metrics to a project, authenticate in the browser/session context and verify the
project's catalog/series endpoints. Use timezone-aware RFC3339 values and a narrow range containing the
ingested point. Confirm a foreign project UUID is not discoverable.

Do not validate tenant isolation with an unscoped ClickHouse query. Any direct diagnostic query must
include the expected project/organization identifiers.

## 5. M3.1 stop condition

M3.1 is complete only after automated/live query tests and the full release gate pass, the changes are
committed and pushed, and:

```text
## main...origin/main
```

is clean. Only then may M3.2 Metrics Explorer UI begin.

## 6. M3.2 frontend matrix

### MX-001 — Real numeric render

Mock a scalar catalog metric plus numeric series response. The explorer must select the numeric metric,
render its observed-point visualization, show returned values/unit, and expose point attributes in the
table.

### MX-002 — Unsupported family honesty

When the catalog contains only histogram/summary-style metrics with `supports_numeric_series=false`,
the UI must explain that no scalar series are available and must not call the numeric series endpoint.

### MX-003 — Exact dimension filters

Entering service/environment values and applying filters must issue the series request with those exact
values together with the selected metric and current bounded time window.

### MX-004 — Dependency/query failure

A rejected series request, including the backend's telemetry-query-unavailable error, must render an
error state. It must not render the empty-series message for the same failure.

### MX-005 — Query-key/project isolation

Catalog and series query keys include the project UUID. The workspace renders the explorer with a key
based on project ID so project switches discard local metric/filter state instead of carrying it into a
different tenant context.

### MX-006 — Bounded rendering

The API remains the primary point-count bound. The plot may represent the returned response while the
HTML point table renders only the latest 100 points and clearly states that subset relative to the
returned count.

### MX-007 — Truncation visibility

When `truncated=true`, the explorer must warn that the visible result is incomplete and recommend a
narrower time range or exact dimension filters.

### MX-008 — Semantic honesty

The frontend must not calculate counter rates, deltas, histogram averages, percentiles, or other derived
metric semantics in M3.2. Mixed service/environment points are shown as observed points rather than one
connected line.

## 7. M3.2 manual explorer smoke

With real OTLP metrics already persisted for a project:

1. open `/orgs/<organization>/projects/<project>/metrics`;
2. confirm the catalog lists the real metric name;
3. select a scalar gauge/sum metric and confirm real ClickHouse points appear;
4. switch among 1h/6h/24h/7d and confirm requests remain bounded;
5. apply an exact service or environment known to exist, then an unmatched value, and verify the
   difference between populated and empty states;
6. remove filters and use Refresh to move the query window to the current time;
7. if possible, stop/unavailable ClickHouse temporarily and confirm the UI shows query failure rather
   than `No numeric points`;
8. switch to another project and confirm the previous metric/filter selection does not carry over.

## 8. M3.2 release gate

Run the focused frontend tests first:

```powershell
docker compose exec web npm test -- --run src/components/MetricsExplorer.test.tsx
```

Then run the full repository release gate:

```powershell
./scripts/verify.ps1
```

Do not commit M3.2 if lint, typecheck, tests, build, backend regression checks, ClickHouse schema
validation, Compose validation, or `git diff --check` is red.

## 9. M3.2 stop condition

M3.2 is complete only after the focused explorer tests, manual real-data smoke, and full release gate are
green; the change is committed and pushed; and:

```text
## main...origin/main
```

is clean. Only then may M3.3 First Dashboard Panels begin.

## 10. M3.3 dashboard configuration/API matrix

### DP-001 — Member list access

A viewer membership can list panel configuration for its own project. The response contains safe
control-plane fields only and never embeds raw telemetry values.

### DP-002 — Write-role enforcement

Owner/admin/editor may create and remove panels. Viewer create/delete attempts return `403` and leave
configuration unchanged.

### DP-003 — Foreign project non-discovery

An exact foreign project UUID returns `404` before dashboard configuration is listed or mutated.

### DP-004 — Panel/project scoping

Deleting `/projects/A/dashboard-panels/<panel-from-B>/` returns `404`; knowing a panel UUID is not enough
to cross project boundaries.

### DP-005 — Duplicate and fan-out bounds

Saving the same metric/range/service/environment query twice is rejected even if the title differs. A
seventh panel is rejected after six have been configured for a project.

### DP-006 — Pin propagation

For an authorized writer, the Metrics explorer sends the selected metric name, active bounded range, and
currently applied exact service/environment filters to the dashboard-panel create endpoint. Viewers do
not receive the pin control.

### DP-007 — Dashboard telemetry reuse

A configured panel calls the existing project numeric-series API with its saved query and `limit=500`.
There is no dashboard-specific raw telemetry endpoint.

### DP-008 — Read states and semantic honesty

Panel loading, error, empty, truncated, and populated states remain distinct. Populated cards may show
latest/min/max over the returned raw number points, but no rate, delta, average-over-time, histogram, or
percentile transformation is introduced.

### DP-009 — Confirmed removal

The browser requires confirmation before calling the delete endpoint. Viewer dashboards remain read-only.

## 11. M3.3 focused release checks

After applying the migration:

```powershell
docker compose exec api /opt/venv/bin/python manage.py migrate
```

Run focused backend and frontend tests:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest apps/projects/tests/test_dashboard_panels.py -v
docker compose exec web npm test -- --run src/components/MetricsExplorer.test.tsx src/components/DashboardPanels.test.tsx
```

Then run the complete repository gate:

```powershell
./scripts/verify.ps1
```

## 12. M3.3 manual real-data smoke

Using a project with a real scalar OTLP metric already visible in Metrics:

1. open the Metrics workspace as owner/admin/editor;
2. select the real scalar metric, choose a bounded range, optionally apply exact service/environment
   filters, and pin the current query;
3. open Dashboards and confirm the new panel appears with the saved metric/range/filter labels;
4. confirm real points from ClickHouse render and latest/min/max correspond to the returned raw points;
5. use Refresh panels and confirm the window moves forward without changing saved configuration;
6. pin the same query again and confirm the UI/API reports the duplicate instead of creating another
   panel;
7. sign in as a viewer where practical and confirm panels remain readable without pin/remove controls;
8. remove a panel as a writer, confirm the browser prompt, and verify the panel disappears after the
   control-plane list refreshes.

## 13. M3.3 stop condition

M3.3 is complete only after the migration, focused backend/frontend tests, manual real-data dashboard
smoke, and full release gate are green; the change is committed and pushed; and:

```text
## main...origin/main
```

is clean. Only then may M3.4 Operational Verification and Documentation begin.

## 14. M3.4 operational closeout

Run from the repository root on Windows/PowerShell:

```powershell
./scripts/verify-m3.ps1
```

The default closeout recreates current Compose containers with build/force-recreate but preserves all
persistent volumes. `-SkipComposeRecreate` and `-SkipReleaseGate` exist only for diagnosing a failed
step; neither switch is acceptable for the final M3 sign-off.

The verifier requires:

- one valid project telemetry API key with `telemetry:write`;
- a normal Sentrix username/password whose membership includes the same project;
- owner/admin/editor role for that browser user so a temporary panel can be created;
- one free dashboard panel slot (the V1 maximum remains six).

`SENTRIX_OTLP_API_KEY` may provide the telemetry key and `SENTRIX_BROWSER_USERNAME` may provide the
username. The browser password is always read with `Read-Host -AsSecureString`. Do not place passwords or
one-time keys in repository files or command history.

## 15. M3.4 runtime assertions

The verifier must prove, in order:

1. Compose configuration is valid and postgres/redis/clickhouse/api/web are running;
2. web, liveness, readiness, and ClickHouse schema checks pass;
3. `otlp_metric_smoke.py` exports a uniquely named raw scalar value through `/v1/metrics`;
4. the helper authenticates the key, scopes its diagnostic by derived organization/project IDs, and
   finds the expected value durably in `sentrix_metrics`;
5. a CSRF/session-authenticated browser user can access that project through normal membership APIs;
6. the fresh metric appears through the project catalog and exact-filter numeric-series API;
7. the verifier creates and re-reads one temporary dashboard panel for the fresh query;
8. the operator opens the printed Metrics and Dashboards URLs and confirms the same fresh metric/value;
9. the temporary panel is deleted (with best-effort cleanup also attempted if a later step fails);
10. the entire `scripts/verify.ps1` release gate passes.

The browser confirmation does not replace API checks. Conversely, the direct ClickHouse persistence
check does not replace the session-authenticated query check.

## 16. Expected M3.4 success

A successful run ends with:

```text
M3 operational verification passed.
```

Then verify repository state:

```powershell
git diff --check
git status -sb
git diff --stat
```

Before the closeout commit, only the intended M3.4 script/documentation cleanup should be present.
Generated `frontend/*.tsbuildinfo` files are ignored and must not be staged.

## 17. M3 stop condition

M3 is complete only after `verify-m3.ps1` passes without its diagnostic skip switches, the closeout
changes are committed and pushed, and:

```text
## main...origin/main
```

is clean. At that point M3.1 query, M3.2 explorer, M3.3 dashboard, and M3.4 operational evidence form one
closed milestone; do not continue adding M3 behavior after sign-off.
