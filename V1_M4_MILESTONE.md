# Sentrix V1 M4 — Logs and Trace Correlation

## 1. Goal

V1 M4 extends the proven telemetry read boundary from metrics to logs and correlated traces. The
milestone starts with a narrow tenant-safe log search API, connects the project Logs workspace to real
ClickHouse rows, then introduces trace lookup/correlation without weakening the existing control-plane
security model.

M4 keeps the same ownership split established by M2/M3:

- Django/PostgreSQL owns users, organizations, projects, memberships, and control-plane configuration;
- ClickHouse owns raw logs and spans;
- first-party browser reads use Django sessions;
- project UUIDs are resource locators, never tenant authority;
- organization/project predicates come only from the authorized Django project.

## 2. User outcome

At M4 completion, an authenticated project member can:

```text
Open project workspace
      |
      +--> Logs
      |     +--> search a bounded time window
      |     +--> filter service/environment/severity
      |     +--> search log body text
      |     +--> inspect log attributes and trace/span IDs
      |     `--> open a correlated trace when one exists
      |
      `--> Traces
            +--> inspect project-scoped trace/span data
            `--> understand parent/child timing without synthetic spans
```

The UI must distinguish empty data from dependency/query failure and must never fabricate correlation.

## 3. Ordered delivery

### M4.1 — Logs query foundation

Deliver:

- session-authenticated project log-search endpoint;
- membership-scoped project resolution before ClickHouse access;
- bounded UTC windows and result limits;
- exact service/environment filters;
- minimum OpenTelemetry severity-number filter;
- bounded case-insensitive body substring search;
- validated exact trace-ID filter for later correlation;
- raw log/resource/scope attributes and correlation IDs in the response;
- HTTP 503 when ClickHouse cannot serve the query;
- automated tests plus a live same-log/two-tenant isolation query;
- synchronized architecture, coding, README, milestone, and testing documentation.

### M4.2 — Logs Explorer UI

After M4.1 is green, committed, and pushed, replace the Logs placeholder with a real project-scoped
explorer backed only by the M4.1 endpoint. The first UI remains read-only and bounded.

### M4.3 — Trace lookup and log-to-trace correlation

After M4.2 is green, committed, and pushed, add project-scoped trace query/detail behavior over
`sentrix_spans`, then allow logs with valid trace IDs to navigate into the corresponding trace. The trace
view must preserve span parentage/timing/status rather than inventing missing spans or cross-tenant links.

### M4.4 — Operational verification and documentation

Close M4 by sending correlated real OTLP logs/traces through the public ingestion path, proving scoped
ClickHouse persistence and browser reads, then running the complete release gate.

## 4. M4.1 API contract

```text
GET /api/v1/projects/{project_id}/logs/search/
```

Supported query parameters:

```text
start                 optional RFC3339 timestamp with timezone
end                   optional RFC3339 timestamp with timezone
limit                 optional; default 200, maximum 1000
service_name          optional exact match
environment           optional exact match
min_severity_number   optional integer 0..24
body_contains         optional case-insensitive substring, maximum 512 characters
trace_id              optional exact 32-hex non-zero OpenTelemetry trace ID
```

The default window is the previous hour. A request may span at most seven days and uses half-open
`[start, end)` bounds. Results are ordered newest-first and the query reads at most `limit + 1` rows so
the response can expose `truncated=true` without an unbounded count.

Response rows preserve:

- event and observed timestamps;
- service and environment;
- instrumentation scope name/version/attributes;
- resource attributes;
- severity number/text;
- body and event name;
- trace/span correlation IDs when valid;
- flags and dropped-attribute count;
- log-record attributes.

The all-zero storage sentinel used for absent trace/span IDs is returned as `null`, not as a usable
correlation identifier.

## 5. M4.1 acceptance

M4.1 is green only when:

- any authenticated project member, including viewers, can search logs for their project;
- foreign/unknown project UUIDs return `404` before ClickHouse is opened;
- every log query includes both authorized `organization_id` and `project_id` predicates;
- time windows remain timezone-aware, half-open, and no longer than seven days;
- result limits are bounded to `1..1000` before query execution;
- service/environment/body/severity/trace values are typed ClickHouse parameters rather than SQL text;
- body search is bounded and case-insensitive but does not become arbitrary regex/query syntax;
- trace IDs are exact 32-hex non-zero identifiers before they reach ClickHouse;
- responses preserve raw log metadata and do not infer missing trace/span relationships;
- ClickHouse failures become HTTP 503 and clients close on success/failure;
- a live integration test sends the same log/trace identifiers to two projects and proves project A
  cannot receive project B's row;
- all M3 ingestion/query/dashboard regressions and the full repository quality gate remain green;
- documentation describes the implemented contract and M4 sequence.

## 6. Explicitly out of scope for M4.1

- Logs Explorer UI;
- trace-list/detail APIs or waterfall rendering;
- arbitrary attribute-expression filters;
- regex or user-provided SQL/query languages;
- full-text/search indexes, projections, materialized views, or retention changes;
- log aggregation, histograms, saved searches, or dashboards;
- alert evaluation, incidents, billing, integrations, or AI analysis.

M4.2 must not begin until M4.1 is green, committed, pushed, and `main` is aligned with `origin/main`.
