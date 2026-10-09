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
