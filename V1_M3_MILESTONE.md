# Sentrix V1 M3 — Metrics Explorer and First Dashboard Panels

## 1. Goal

V1 M3 turns the durable metrics written in M2 into a trustworthy read experience. The milestone adds a
tenant-safe metrics query boundary, connects the project Metrics workspace to real telemetry, and then
reuses that query contract for the first read-only dashboard panels.

M3 does not weaken the V1 control-plane/data-plane split:

- Django/PostgreSQL owns users, organizations, projects, membership/RBAC, and dashboard configuration;
- ClickHouse owns raw telemetry and telemetry reads;
- browser sessions authorize first-party query requests;
- project UUIDs locate resources but never establish tenant authority.

## 2. User outcome

At M3 completion, an authenticated project member can:

```text
Open project workspace
      |
      v
Metrics
      |
      +--> discover recently observed metrics
      +--> choose a numeric metric
      +--> select a bounded time range
      +--> filter by service/environment
      +--> inspect real points from ClickHouse
      |
      v
Dashboard
      |
      `--> view first project-scoped metric panels
```

The UI must show empty/error/unavailable states truthfully and must never synthesize telemetry.

## 3. Ordered delivery

### M3.1 — Metrics query foundation

Deliver:

- session-authenticated project metrics catalog endpoint;
- session-authenticated project numeric-series endpoint;
- membership-scoped project resolution before ClickHouse access;
- typed ClickHouse query parameters;
- bounded UTC time windows and result limits;
- exact service/environment series filters;
- HTTP 503 for ClickHouse query failure;
- unit/security tests plus a live ClickHouse tenant-isolation query;
- synchronized README, architecture, coding, milestone, and testing documentation.

### M3.2 — Metrics Explorer UI

After M3.1 is green, committed, and pushed, replace the Metrics placeholder with a real explorer using
only the M3.1 API. The explorer should include metric selection, time-range controls, service/environment
filters, loading/empty/error states, and a first numeric visualization/table without inventing rate or
histogram semantics.

### M3.3 — First dashboard panels

After M3.2 is green, committed, and pushed, add the first read-only project dashboard panels backed by
the same query boundary. Dashboard configuration belongs to the control plane; telemetry values still
come from ClickHouse. Panel authoring remains intentionally narrow until query semantics are proven.

### M3.4 — Operational verification and documentation

Close M3 by proving the query/explorer/dashboard path against real OTLP metrics in a clean Compose
stack and running the complete backend/frontend/repository release gate.

## 4. M3.1 API contract

```text
GET /api/v1/projects/{project_id}/metrics/catalog/
GET /api/v1/projects/{project_id}/metrics/series/
```

Common query behavior:

- `start` and `end` are optional timezone-aware RFC3339 timestamps;
- the default window is the previous hour;
- windows are half-open `[start, end)` and may not exceed seven days;
- foreign/unknown projects return `404` before ClickHouse is queried.

Catalog:

- default limit: 100;
- maximum limit: 500;
- returns name, description, unit, observed metric/value types, point count, latest observation time,
  and whether scalar numeric series are currently supported.

Numeric series:

- requires `metric_name`;
- optional exact `service_name` and `environment` filters;
- default limit: 2,000 points;
- maximum limit: 5,000 points;
- reads only rows whose `number_value` is present;
- returns timestamp, service/environment, metric type, aggregation temporality, monotonicity, value
  type/value, point attributes, and a truncation flag.

## 5. M3.1 acceptance

M3.1 is green only when:

- authenticated project members, including viewers, can read metrics for their projects;
- foreign project UUIDs return `404` and do not open a ClickHouse query;
- organization/project identity used in ClickHouse comes only from the authorized Django project;
- invalid/naive/reversed/over-seven-day time windows are rejected with HTTP 400;
- catalog/series limits are bounded before query execution;
- metric/service/environment values are parameterized rather than interpolated into SQL;
- catalog metadata preserves non-scalar metric families without pretending they are numeric;
- series returns scalar number points without inventing counter rates or histogram averages;
- ClickHouse failures return HTTP 503 and clients are closed on failure;
- a live integration test proves one tenant cannot receive another tenant's same-named metric points;
- M2 ingestion and all existing backend/frontend release gates remain green;
- documentation reflects the implemented query contract and M3 sequence.

## 6. Explicitly out of scope for M3.1

- Metrics Explorer UI/charting;
- dashboard panels or dashboard persistence;
- server-side rate/delta functions;
- histogram heatmaps/quantiles or summary visualization;
- arbitrary attribute-expression query language;
- logs/traces query APIs;
- retention TTLs, rollups, projections, materialized views, or speculative ClickHouse optimization;
- alert evaluation, incidents, billing, or AI analysis.

M3.2 must not begin until M3.1 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 7. M3.2 — Metrics Explorer UI

M3.2 replaces the project Metrics placeholder with a first-party explorer backed only by the M3.1
catalog and numeric-series APIs. The browser does not query ClickHouse directly and does not add a
parallel metric semantics layer.

Explorer behavior:

- project-scoped catalog discovery;
- automatic selection of the first scalar metric when available;
- 1 hour, 6 hour, 24 hour, and 7 day bounded windows;
- explicit refresh anchored to the current time;
- exact service/environment filters;
- observed-point visualization plus latest-point table;
- visible metric type/value/unit/catalog count metadata;
- explicit loading, empty, error, unsupported-family, and truncated states.

## 8. M3.2 acceptance

M3.2 is green only when:

- the `/metrics` workspace route renders real catalog state instead of the placeholder;
- browser requests use the immutable active project UUID and the M3.1 endpoints;
- query keys include project, start/end, selected metric, and applied dimension filters;
- switching project context resets/remounts the explorer state;
- numeric gauge/sum metrics can be selected and their returned points are visible in a plot and table;
- histogram/exponential-histogram/summary-only metrics are visible but cannot be selected as scalar
  series;
- no browser rate/delta/average/percentile/histogram calculation is introduced;
- exact service/environment filters are passed to the series query;
- loading, no-catalog-data, no-series-data, query-error, and truncated-result states remain distinct;
- the first plot does not connect points that may belong to separate service/environment series;
- the point table exposes timestamp, value, service, environment, type, and attributes and bounds the
  rendered row count;
- frontend tests cover rendering, unsupported families, filter propagation, and query failure;
- all backend/frontend/infrastructure release gates remain green;
- README, architecture, coding guideline, milestone, and testing docs describe the explorer contract.

## 9. Explicitly out of scope for M3.2

- dashboard panels or dashboard persistence;
- metric aggregation/group-by controls;
- counter-rate or delta derivation;
- histogram heatmaps, percentiles, or summary quantile visualization;
- arbitrary attribute query expressions;
- URL-persisted/shareable explorer state;
- logs/traces explorers, alert evaluation, retention changes, billing, or AI analysis.

M3.3 must not begin until M3.2 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 10. M3.3 — First read-only dashboard panels

M3.3 reuses the M3.1 query boundary and M3.2 observed-point visualization to add the first project
Dashboards experience. Dashboard configuration is explicit control-plane state rather than an implicit
choice of whichever metric happens to appear first in ClickHouse.

The V1 configuration model is intentionally narrow:

```text
ProjectDashboardPanel
  project_id
  title
  metric_name
  time_range: 1h | 6h | 24h | 7d
  service_name (optional exact filter)
  environment (optional exact filter)
  position
  created_by / timestamps
```

One project has one dashboard surface with at most six configured panels. Writers pin the current scalar
Metrics explorer query; all project members can view resulting panels. Telemetry values are never stored
in the panel model.

Control-plane endpoints:

```text
GET    /api/v1/projects/{project_id}/dashboard-panels/
POST   /api/v1/projects/{project_id}/dashboard-panels/
DELETE /api/v1/projects/{project_id}/dashboard-panels/{panel_id}/
```

Each rendered panel calls the existing M3.1 numeric-series endpoint with its saved bounded range and
exact filters, capped at 500 points.

## 11. M3.3 acceptance

M3.3 is green only when:

- panel configuration is persisted in PostgreSQL and contains no telemetry values;
- any authenticated project member, including viewers, can list the project's dashboard panels;
- only owner/admin/editor memberships can create/remove panel configuration;
- foreign project UUIDs return `404` and panel deletion is scoped to both route project and panel UUID;
- duplicate metric/range/filter queries are rejected and a project cannot exceed six panels;
- the Metrics explorer can pin its selected scalar metric, current 1h/6h/24h/7d range, and applied exact
  filters without accepting arbitrary query syntax;
- the `/dashboards` workspace renders configured panels instead of the placeholder;
- dashboard telemetry reads reuse the existing project metrics-series API and request at most 500 points
  per panel;
- project changes remount the dashboard and all query keys remain project/panel/window specific;
- a panel distinguishes loading, query failure, empty data, truncation, and populated states;
- populated panels expose raw latest/min/max/point-count summaries plus the observed-point plot without
  deriving rate/delta/histogram/percentile semantics;
- viewers receive no pin/remove controls even though backend authorization remains authoritative;
- backend tests cover tenant/RBAC/scoping/duplicate/limit behavior and frontend tests cover pinning,
  rendering, viewer read-only behavior, empty dashboards, and confirmed removal;
- migration drift, backend/frontend quality gates, ClickHouse schema validation, Compose validation, and
  `git diff --check` remain green;
- README, architecture, coding guideline, milestone, and testing docs describe the control-plane panel
  boundary and the narrow V1 dashboard contract.

## 12. Explicitly out of scope for M3.3

- multiple named dashboards;
- drag/drop layout or panel resizing/reordering;
- free-form panel/query editors;
- arbitrary attribute expression filters or group-by controls;
- counter rate/delta functions, histogram/percentile/summary transformations;
- dashboard-specific ClickHouse tables, rollups, caches, or materialized views;
- dashboard sharing/public links;
- logs/traces panels, alerts, incidents, billing, or AI analysis.

M3.4 must not begin until M3.3 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 13. M3.4 — Operational verification and milestone closeout

M3.4 adds no product feature. It proves that the M2 ingestion path and M3 read/dashboard path operate
together against a freshly recreated, volume-preserving Compose stack.

The closeout flow is:

```text
real project API key
      |
      v
unique OTLP metric -> durable ClickHouse row
      |
      v
normal browser session -> catalog -> numeric series
      |
      v
temporary persisted dashboard panel
      |
      v
human confirmation in Metrics + Dashboards
      |
      v
temporary panel cleanup -> full repository release gate
```

`backend/scripts/otlp_metric_smoke.py` exports one uniquely named scalar metric through `/v1/metrics`,
authenticates the supplied key to derive organization/project identity, and verifies scoped durable
persistence. It emits only non-secret metadata needed by `scripts/verify-m3.ps1`.

`verify-m3.ps1` then establishes a normal browser session, proves the fresh metric through the M3.1
catalog/series APIs, creates one temporary M3.3 dashboard panel, requires browser confirmation of the
fresh value in both routes, removes the temporary panel, and runs `scripts/verify.ps1`.

## 14. M3.4 acceptance

M3 is closed only when:

- Compose services are recreated from the current repository without deleting persistent volumes;
- frontend, liveness, readiness, and ClickHouse schema checks are green;
- a real project credential exports a fresh unique OTLP/HTTP scalar metric;
- a scoped ClickHouse diagnostic proves the metric is durable for the organization/project derived from
  that credential;
- a separately authenticated browser user can resolve the same project through membership;
- the session-authenticated catalog exposes the fresh metric as numeric and the numeric-series endpoint
  returns the expected raw value using exact service/environment filters;
- an owner/admin/editor session can create and read one temporary dashboard panel for that exact query;
- the operator confirms the fresh metric/value appears in both the real Metrics and Dashboards routes;
- the temporary dashboard panel is removed after the smoke while the telemetry row is left untouched;
- the complete `scripts/verify.ps1` backend/frontend/schema/build/repository gate passes afterward;
- no bearer credential/password is printed or persisted by the verifier;
- generated TypeScript build metadata is not tracked and the final working tree can be clean;
- README, architecture, coding, milestone, and testing docs describe the completed M3 contract.

## 15. M3 closeout boundary

M3 completion does not authorize additional query semantics or product scope. Counter rates/deltas,
histogram percentiles, arbitrary grouping/query languages, logs/traces explorers, dashboard layout
editing, alerts, incidents, retention/rollups, billing, and AI analysis remain future work.

After M3.4 is green, commit/push the closeout and confirm `main` is aligned with `origin/main`. Only then
should the next V1 milestone begin.
