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


## 7. M4.2 — Logs Explorer UI

M4.2 replaces the project Logs placeholder with a read-only explorer that uses only the M4.1 endpoint.
It does not add a second telemetry query implementation or direct browser access to ClickHouse.

The explorer supports:

- 1h, 6h, 24h, and 7d UTC windows;
- bounded result limits of 100, 200, 500, or 1000 rows;
- manual refresh of the current window;
- exact service and environment filters;
- minimum OpenTelemetry severity thresholds;
- bounded case-insensitive body substring input;
- exact trace-ID input;
- newest-first raw log rows with severity/body/service/environment;
- trace/span IDs plus raw scope/resource/log attributes in inspectable details;
- distinct loading, healthy-empty, query-error, and truncated states.

Draft filters are local form state. Requests change only when filters are applied/cleared, the time range
or result limit changes, or the operator explicitly refreshes.

## 8. M4.2 acceptance

M4.2 is green only when:

- `/logs` renders real rows from the M4.1 API instead of the placeholder;
- query keys contain project UUID, explicit time bounds, row limit, and every applied filter;
- switching projects remounts the explorer so log/filter state cannot bleed between tenants;
- browser controls stay within the server's seven-day and 1000-row maximums;
- typing in filter fields does not issue a request until Apply is used;
- service/environment/severity/body/trace values propagate exactly through the existing API client;
- trace/span IDs remain non-navigable text until M4.3 establishes the span query boundary;
- raw attributes/body are rendered as text and no correlation or message semantics are fabricated;
- loading, empty, error, and truncated results are visibly distinct;
- frontend tests cover rendering, filter propagation, healthy empty state, truncation, and query failure;
- the complete repository release gate remains green and documentation is synchronized.

## 9. Explicitly out of scope for M4.2

- trace lookup/detail APIs or clickable trace navigation;
- trace waterfall rendering;
- arbitrary attribute expressions, regex, or user-provided query languages;
- saved searches, log aggregations/charts, dashboards, or export;
- ClickHouse index/projection/retention changes;
- alerts, incidents, billing, integrations, or AI analysis.

M4.3 must not begin until M4.2 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 10. M4.3 — Trace lookup and log-to-trace correlation

M4.3 adds the first trace read boundary over `sentrix_spans` and connects correlated log rows to it.
The backend contract is intentionally an exact trace lookup rather than an unbounded trace-search API:

```text
GET /api/v1/projects/{project_id}/traces/{trace_id}/
```

Supported query parameters:

```text
start   optional RFC3339 timestamp with timezone
end     optional RFC3339 timestamp with timezone
limit   optional; default 500, maximum 1000 spans
```

The trace ID must be a non-zero 32-character hexadecimal OpenTelemetry trace ID. The default lookup
window is the previous hour, a request may span at most seven days, and the time predicate is half-open
`[start, end)`. Spans are ordered by observed `start_time` and then span ID. The query reads `limit + 1`
rows so truncation is explicit without an unbounded count.

Responses preserve raw span timing, service/environment, scope/resource/span attributes, trace/span/
parent IDs, trace state, span kind, status, flags, dropped counts, and the stored event/link JSON. The
all-zero parent/span sentinel is returned as `null`; missing parents are never synthesized.

The Logs explorer creates an **Open trace** link only for a non-zero trace ID returned by M4.1. The link
carries the same bounded start/end window as the log query, while the Traces workspace independently
re-authorizes the project before reading `sentrix_spans`.

## 11. M4.3 acceptance

M4.3 is green only when:

- any authenticated project member, including viewers, may read a trace for a project they can access;
- foreign/unknown project UUIDs return `404` before ClickHouse is opened;
- trace IDs are validated as exact non-zero 32-hex values before query execution;
- every span query includes authorized `organization_id` and `project_id` plus typed trace/time values;
- windows are timezone-aware, half-open, and no longer than seven days;
- span limits are bounded to `1..1000` and truncation is explicit;
- raw start/end/duration, parentage, status, attributes, events, links, flags, and dropped counts survive
  the read boundary without inferred spans or synthetic relationships;
- ClickHouse failure becomes HTTP `503`, healthy no-match becomes an empty span list, and clients close
  on success/failure;
- a live integration test writes the same trace ID into two projects and proves project-scoped lookup;
- `/traces` supports exact trace-ID lookup and visibly distinguishes loading, empty, error, and truncated
  states;
- the trace view shows actual parent IDs and marks a parent absent from the bounded response rather than
  fabricating it;
- a correlated log can navigate to the project Traces workspace with the log query's bounded window;
- frontend tests cover linked lookup, input validation, raw span rendering, missing-parent honesty,
  truncation, and query failure;
- the complete repository release gate remains green and documentation is synchronized.

## 12. Explicitly out of scope for M4.3

- unbounded trace catalogs, service-wide trace search, or arbitrary attribute query languages;
- derived critical-path analysis, latency attribution, or synthetic/missing spans;
- service maps or cross-trace aggregation;
- ClickHouse index/projection/materialized-view/retention changes without measured need;
- saved trace searches, trace dashboards, alerts, incidents, billing, integrations, or AI analysis.

M4.4 operational closeout must not begin until M4.3 is green, committed, pushed, and `main` is aligned
with `origin/main`.

## 13. M4.4 — Operational verification and documentation closeout

M4.4 adds no new product query semantics. It packages the already-proven M4 ingestion/read/browser
boundaries into one reproducible closeout command:

```powershell
./scripts/verify-m4.ps1
```

By default the verifier rebuilds and force-recreates the current Compose services while preserving
PostgreSQL and ClickHouse volumes, waits for frontend/API readiness, validates the ClickHouse schema,
then securely prompts for an existing project telemetry key.

`backend/scripts/otlp_log_trace_smoke.py` authenticates that key to derive the organization/project
identity, generates one unique trace with a real root/child parent relationship plus one ERROR log
correlated to the child span, and sends both binary OTLP payloads through `/v1/traces` and `/v1/logs`.
It then performs tenant-scoped ClickHouse diagnostics using both credential-derived IDs, the exact trace
ID, service/environment, and a narrow UTC window. No row is inserted directly by verification.

The PowerShell verifier separately establishes a normal CSRF/session-authenticated browser API session.
That user must independently have membership in the telemetry-key project. It verifies the fresh row
through `/logs/search/`, verifies the same trace through `/traces/{trace_id}/`, and checks the returned
correlation IDs, root/child parentage, status, smoke attributes, and event JSON before asking for one
human Logs -> **Open trace** browser confirmation.

No temporary PostgreSQL configuration is created by M4.4. The unique smoke telemetry remains in
ClickHouse as ordinary observed data. After browser confirmation, the verifier runs the full
`scripts/verify.ps1` release gate unless `-SkipReleaseGate` is explicitly used while debugging.
`-SkipComposeRecreate` is likewise a debugging convenience and is not the final closeout path.

## 14. M4.4 acceptance

M4.4 is green only when:

- Compose configuration is valid and the required PostgreSQL, Redis, ClickHouse, API, and web services
  are running from the current repository without deleting persistent volumes;
- liveness, readiness, and live ClickHouse schema validation pass;
- the telemetry key is read from a secure prompt/stdin path and is never printed or committed;
- the smoke derives organization/project identity from the authenticated key rather than telemetry
  attributes or caller-supplied tenant IDs;
- a unique correlated trace and log are accepted through the public OTLP/HTTP endpoints;
- project-scoped ClickHouse verification proves the expected two spans plus correlated log, including
  real root/child parentage, span status, event data, service/environment, and smoke markers;
- a separately authenticated browser/session user can resolve that same project through membership;
- the session-authenticated log API returns exactly the fresh correlated row using bounded exact filters;
- the session-authenticated trace API returns the same trace with the real root/child relationship and
  no synthetic span;
- the real Logs workspace shows the fresh row, **Open trace** navigates to Traces, and the expected trace
  renders correctly;
- the complete repository release gate passes after the operational smoke;
- generated `frontend/tsconfig.app.tsbuildinfo` state is no longer tracked, so verification/build output
  does not dirty the repository;
- documentation describes the final M4 runtime and closeout procedure.

## 15. M4 definition of done

V1 M4 is complete only after M4.1 through M4.4 are committed and pushed, the production-shaped M4.4
verification passes without skip flags, and the repository finishes with:

```text
## main...origin/main
```

At that point Sentrix has a tenant-safe, bounded logs explorer plus exact trace inspection and real
log-to-trace correlation over durable ClickHouse telemetry. Broader trace search, service maps, derived
critical-path analysis, log aggregation, retention tuning, and alerting remain later work rather than
implicit M4 behavior.
