# Sentrix Coding Guideline

## 1. Purpose

This document defines the engineering rules for Sentrix. The goal is predictable code, explicit tenant boundaries, testable APIs, and an architecture that can grow from a modular monolith into independently scaled telemetry services without rewriting the control plane.

These rules apply to production code, migrations, tests, scripts, Docker configuration, and documentation.

## 2. Core principles

### 2.1 Correctness before abstraction

Prefer a small explicit implementation over an abstraction whose future use is speculative. Extract shared behavior after there are concrete repeated cases.

### 2.2 Tenant isolation is a backend invariant

Every organization-owned or project-owned read/write must derive authorization from the authenticated user and stored membership records.

Do not write code equivalent to:

```python
Project.objects.get(id=request.data["project_id"])
```

when the resource is tenant-owned.

Use a scoped queryset or service:

```python
Project.objects.filter(
    id=project_id,
    organization__memberships__user=request.user,
).get()
```

Frontend routing, hidden controls, or a supplied organization ID are never proof of authorization.

### 2.3 Keep the control plane and data plane separate

PostgreSQL is for relational control-plane state such as users, organizations, projects, permissions, dashboards, alert definitions, integrations, audit metadata, and billing configuration.

ClickHouse is for high-volume telemetry and analytical data.

Do not add raw metrics, log events, spans, or unbounded telemetry payloads to Django models without an architecture decision record explaining why.

### 2.4 Make failure visible

External dependencies must have bounded timeouts and errors must be observable. Do not silently catch exceptions unless the failure is intentionally degraded and is recorded through logs/metrics.

### 2.5 Tests are part of the feature

A behavior change without corresponding test coverage is incomplete. Regression fixes should include a test that fails before the fix and passes after it.

## 3. Python and Django

### 3.1 Runtime

- Python: `>=3.14,<3.15`
- Django: `>=6.1.1,<6.2`
- Package management: `uv`
- Formatting/linting: Ruff
- Static analysis: mypy
- Generated Django migration files are excluded from Ruff; migration correctness is enforced with Django migration checks and tests.
- Tests: pytest + pytest-django

Do not add a dependency when the standard library or an existing dependency is sufficient.

### 3.2 Style

- Maximum line length: 100 characters.
- Use type hints for public functions, services, selectors, and non-trivial helpers.
- Prefer `pathlib.Path` over manual path concatenation.
- Prefer timezone-aware datetimes.
- Prefer UUID primary keys for externally visible domain entities.
- Use enums/`TextChoices` for stable state machines.
- Do not use wildcard imports.
- Avoid module-level mutable state.
- Keep views thin; place reusable domain logic in services/selectors.

### 3.3 Django app boundaries

Each app owns one domain concept. A typical structure is:

```text
apps/<domain>/
├── admin.py
├── apps.py
├── models.py
├── permissions.py
├── selectors.py
├── serializers.py
├── services.py
├── urls.py
├── views.py
└── tests/
```

Not every app needs every file. Do not create empty architectural ceremony.

Recommended responsibilities:

- `models.py`: persistence and local invariants.
- `selectors.py`: reusable read/query logic.
- `services.py`: write workflows and cross-model business operations.
- `permissions.py`: DRF authorization primitives.
- `serializers.py`: request/response validation and representation.
- `views.py`: HTTP orchestration only.

### 3.4 Models and migrations

- Schema changes and migrations are committed together.
- Migrations must be deterministic and reviewable.
- Do not edit an applied migration in a shared environment; create a new migration.
- Every tenant-owned model has an explicit organization/project relationship or an unambiguous path to one.
- Add database constraints for invariants that must survive concurrent writes.
- Add indexes based on known query patterns, not guesses.

### 3.5 Transactions

Use `transaction.atomic()` for workflows that must commit together. Do not hold database transactions while calling remote services.

For concurrent state transitions, prefer database constraints, conditional updates, or `select_for_update()` where needed.

### 3.6 APIs

- API prefix: `/api/v1/`.
- Use nouns for resources.
- Return stable error shapes.
- Validate request payloads through serializers/forms, not ad-hoc dictionary access.
- Pagination is mandatory for collections that can grow without a hard upper bound.
- Do not expose internal exception messages to clients.
- Breaking API changes require a versioning decision.

A recommended error body is:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have access to this project."
  }
}
```

### 3.7 Authentication and authorization

V1 M1 uses secure Django session authentication for the browser application.

Rules:

- CSRF protection remains enabled.
- Cookies are `HttpOnly`; secure cookies are mandatory in deployed HTTPS environments.
- Login endpoints are rate-limited before public deployment.
- Permission checks occur in API code even when the UI also hides actions.
- Role checks must use named role/permission helpers rather than string comparisons scattered through views.

V1 M2 machine credentials follow additional rules:

- API keys are project-scoped control-plane records and resolve to exactly one project/organization.
- Store only a public prefix and a one-way hash of the secret; never persist the full token.
- Return the full token only from the create response; list responses never expose `secret_hash`.
- Initial machine scope is `telemetry:write`; add scopes only for concrete capabilities.
- Revocation is metadata-preserving through `revoked_at`, not hard deletion.
- Optional expiry must be validated as a future timestamp.
- `last_used_at` is updated only after successful machine authentication; M2.1 does not fabricate use.
- Owner/admin/editor may manage project keys; viewers and foreign-tenant callers may not.

### 3.8 Logging

Use Python logging with structured context when available.

Never log:

- passwords
- session cookies
- CSRF tokens
- API key secrets
- OAuth tokens
- raw authorization headers
- unrestricted telemetry payloads

Useful request context includes request ID, user ID, organization ID, project ID, operation, duration, and outcome.

## 4. React and TypeScript

### 4.1 Runtime and tooling

- React 19.3
- TypeScript 5.x
- Vite 8.3+
- React Router
- TanStack Query for server state
- Vitest 5 for unit/component tests
- ESLint for linting

### 4.2 TypeScript rules

- `strict` mode remains enabled.
- Avoid `any`. If unavoidable at a boundary, isolate and validate it.
- Prefer `unknown` for untrusted values.
- API response types live near the API client or feature using them.
- Do not duplicate backend enums manually without an explicit synchronization strategy.

### 4.3 Component rules

Prefer small components with clear ownership. Business behavior belongs in hooks/services, not giant page components.

Recommended feature structure:

```text
src/features/projects/
├── api.ts
├── components/
├── hooks.ts
├── pages/
├── types.ts
└── tests/
```

### 4.4 Server state

Use TanStack Query for data fetched from the API. Do not copy remote server state into global client stores without a concrete need.

Cache keys must include the tenant context where relevant, for example:

```ts
["projects", organizationId]
```

Changing organizations/projects must invalidate or isolate data so information from one tenant is not displayed under another tenant context.

### 4.5 Forms

Validate on both client and server. Client validation improves feedback; server validation is authoritative.

### 4.6 Accessibility

Interactive controls must be keyboard accessible, labelled, and usable without relying only on color. Charts added in later milestones must provide textual/summary alternatives where practical.

## 5. Security rules

The following are required before internet-facing deployment:

- HTTPS only.
- secure cookies.
- strict allowed-host/origin configuration.
- CSRF enabled for browser sessions.
- rate limiting on authentication and ingestion endpoints.
- request body limits.
- secret rotation procedure.
- dependency vulnerability scanning.
- least-privilege database users.
- no public ClickHouse/PostgreSQL/Redis ports in production.
- audit logging for privileged actions.

Secrets belong in environment/secret managers, never source control.

## 6. ClickHouse and telemetry rules

V1 M1 only establishes connectivity. V1 M2 telemetry implementation must follow these rules:

- Every row includes tenant identifiers required for enforcement and query pruning.
- Ingestion validates tenant credentials before accepting data.
- Time-based partitioning and TTLs are storage-engine responsibilities.
- High-cardinality dimensions are reviewed deliberately.
- Queries always include bounded time ranges unless a privileged internal operation explicitly requires otherwise.
- Query limits and timeouts protect the cluster from unbounded scans.
- Raw telemetry schemas are versioned.

## 7. Redis rules

Redis is ephemeral infrastructure unless a feature explicitly documents persistence requirements.

Appropriate uses include caching, locks, throttling, short-lived coordination, and future queue/broker workloads.

Do not store the only copy of durable domain state in Redis.

## 8. Testing expectations

Backend changes should cover:

- happy path
- unauthorized request
- authenticated but wrong-tenant request
- role boundary when relevant
- validation failure
- important uniqueness/constraint behavior

Frontend changes should cover important behavior and user-visible states rather than implementation details.

See `V1_MILESTONE_TESTING.md` for the release gate.

## 9. Git and commit discipline

Keep commits scoped and reviewable. A commit should leave the repository in a buildable/testable state whenever possible.

Recommended conventional prefixes:

```text
feat:     user-visible capability
fix:      defect correction
docs:     documentation only
test:     test-only change
refactor: behavior-preserving code change
chore:    tooling/dependency/maintenance
ci:       continuous-integration change
```

Examples:

```text
feat(organizations): add tenant membership model
fix(projects): enforce membership in project detail queries
test(auth): cover CSRF-protected login flow
docs: document V1 control-plane boundary
```

Do not mix mass formatting with behavior changes.

## 10. Pull request checklist

A change is ready for review when:

- [ ] scope is clear and unrelated changes are excluded
- [ ] backend tenant checks are explicit
- [ ] migrations are included where required
- [ ] backend tests pass
- [ ] frontend tests pass where affected
- [ ] Ruff and mypy pass
- [ ] ESLint and TypeScript checks pass
- [ ] no secrets or generated credentials are committed
- [ ] docs are updated when behavior/setup/architecture changes
- [ ] new external dependencies have a concrete reason
- [ ] failure paths and observability have been considered

## 11. Definition of done

A feature is done only when its production behavior, authorization, tests, configuration, and documentation agree. Code that works only through a developer's local manual sequence is not complete.

## 12. Tenant-aware frontend routing

Project workspace URLs use organization/project slugs for navigation, never authorization.

Required rules:

- resolve workspace slugs only against organization/project data returned by authenticated,
  tenant-scoped API calls;
- never call an unscoped backend endpoint because a slug appeared in the URL;
- keep immutable UUIDs as backend/data-plane identifiers even when browser URLs use slugs;
- when organization/project context changes, navigate to a new canonical route instead of retaining
  stale tenant state;
- TanStack Query cache keys must remain tenant-safe as query scope becomes more granular;
- unknown or inaccessible organization/project route combinations render an unavailable state and
  must not reveal whether a foreign tenant resource exists;
- owner/admin/editor UI may expose project-write actions while viewer UI is read-only, but every
  write still requires backend role enforcement.

Workspace section routes may be created before their telemetry implementation only when the UI makes
their unavailable/not-connected state explicit. Do not render sample telemetry in production paths
to make an unfinished data-plane feature appear complete.

## 12. Tailwind and Sentrix visual-system rules

The frontend uses Tailwind CSS 4 with the official Vite plugin. Keep theme configuration in `frontend/src/theme.css` using `@theme`; do not add a legacy
`tailwind.config.js` unless a concrete capability requires it.

Rules:

- reuse Sentrix theme tokens instead of introducing one-off hex values in React components;
- prefer Tailwind utilities in markup for new components and `@apply` for existing shared semantic
  classes when incremental migration keeps the component API clearer;
- keep operational screens dense: avoid oversized cards, excessive vertical whitespace, and large
  decorative headings that reduce information density;
- primary actions use the restrained signal-teal family; violet is secondary emphasis, not a competing primary;
- avoid pure-white body text, black-on-neon controls, and decorative glow that produces unnecessary eye strain;
- normal, muted, helper, placeholder, and disabled labels must remain readable on their actual surface; do not make important text disappear by stacking low-opacity text on dark backgrounds;
- warning/read-only, success, and error states use their semantic tokens and never rely on color alone;
- target WCAG AA contrast for normal interactive and informational text while keeping the palette visually soft;
- focus-visible states must remain obvious for keyboard users;
- responsive layouts must preserve tenant/project context and action discoverability;
- CSS visibility/disabled state is never authorization; backend permission checks remain mandatory.


## 13. Machine authentication implementation rules

V1 M2.2 introduces the reusable machine-authentication primitive. These rules are mandatory for every
endpoint that consumes a project API key:

- machine authentication must be explicitly enabled on the endpoint; do not add project API keys to
  global DRF authentication defaults;
- accept project credentials only through the Bearer authorization scheme and validate the Sentrix
  token shape before database lookup;
- verify the secret with Django's password-hashing API; never compare plaintext secrets directly;
- reject unknown, revoked, and expired credentials with a generic authentication failure;
- derive `organization_id`, `project_id`, `api_key_id`, and scopes from the persisted credential rather
  than caller-supplied tenant identifiers;
- update `last_used_at` only after the secret and credential state authenticate successfully;
- enforce endpoint capabilities with named scope permissions after authentication;
- a valid credential without a required scope is an authorization failure, not an authentication
  failure;
- keep browser session authentication and machine authentication separate trust paths;
- never log the bearer value, raw secret, stored hash, or unrestricted request payload.

The initial required telemetry capability remains `telemetry:write`. Additional scopes require a real
endpoint capability and corresponding tests; do not create speculative permission matrices.

## 14. OTLP/HTTP protocol-boundary rules

M2.3 introduces the first public telemetry protocol boundary. Required rules:

- keep OTLP routes at `/v1/metrics`, `/v1/logs`, and `/v1/traces`; do not nest them under the Sentrix
  control-plane `/api/v1/` namespace;
- authenticate before parsing telemetry bodies and derive tenant identity exclusively from the project key;
- accept only protocol encodings that are implemented faithfully; M2.3 accepts binary protobuf and
  does not approximate OTLP/JSON with generic protobuf JSON parsing;
- use official OpenTelemetry generated protobuf message classes instead of hand-written wire models;
- support `identity` and `gzip` request encodings and enforce the configured size limit after
  decompression;
- return non-retryable 4xx statuses for bad data, unsupported encodings, and oversized payloads as
  appropriate; use 503 when a valid batch cannot be durably accepted;
- never return OTLP success for non-empty telemetry that has only been decoded and then discarded;
- keep the decoder independent of ClickHouse schema/SQL so M2.4 can add storage without changing the
  external protocol contract;
- never log raw bearer credentials or unrestricted telemetry payloads.


## 15. ClickHouse telemetry-schema rules

M2.4 establishes the first durable telemetry schema. Required rules:

- manage telemetry tables through explicit ClickHouse schema code/commands, not Django models or
  PostgreSQL migrations;
- every telemetry table carries `schema_version`, `organization_id`, and `project_id`;
- physical sorting keys begin with tenant/project identity before signal-specific dimensions;
- time-partition raw telemetry by month unless measured behavior justifies a different partition;
- do not add TTLs, projections, codecs, or skip indexes speculatively;
- metric storage must preserve the distinction between number, histogram, exponential-histogram, and
  summary data instead of coercing all values into one scalar;
- trace and span identifiers use fixed-width lowercase-hex storage contracts suitable for correlation;
- keep ClickHouse DDL independent from the OTLP HTTP decoder;
- M2.4 may create/validate tables but must not acknowledge non-empty OTLP requests until M2.5 wires a
  durable write path;
- schema validation must compare live columns/types and partition/sort keys before M2.4 is accepted.

## 16. Telemetry persistence rules

M2.5 activates ClickHouse writes. Required rules:

- derive tenant identifiers only from `OtlpBatch` authentication context, never OTLP attributes;
- normalize telemetry before opening the ClickHouse write transaction/client so malformed internal
  transformations fail visibly rather than being disguised as infrastructure outages;
- acknowledge a non-empty OTLP request only after the corresponding ClickHouse insert succeeds;
- translate ClickHouse connection/insert failures into retryable sink-unavailable behavior;
- write metrics one row per data point and preserve the family-specific fields defined by schema v1;
- convert trace/span IDs to fixed-width lowercase hexadecimal strings before storage;
- preserve resource, instrumentation-scope, and record attributes without promoting arbitrary
  high-cardinality keys into dedicated columns;
- keep the HTTP decoder, normalization layer, and ClickHouse DDL as separate modules;
- tests for persistence must use unique tenant/project IDs and query using those tenant keys;
- include at least one real OpenTelemetry SDK/exporter interoperability test rather than relying only
  on hand-built protobuf fixtures.

## 17. Project API-key UI rules

M2.6 exposes sensitive credential lifecycle through the first-party browser. Required rules:

- API-key list queries must include the immutable project UUID in the TanStack Query key;
- viewer workspaces must not issue API-key management requests merely to discover that the backend
  will reject them;
- create/list/revoke authorization remains a backend responsibility even when controls are hidden or
  disabled in the browser;
- never place a newly created raw API-key secret in TanStack Query cache data, browser storage, URLs,
  analytics, or logs;
- keep the one-time secret only in transient component state and clear it when dismissed or when
  project context changes;
- list views may display only safe metadata returned by the list endpoint: prefix, scopes, expiry,
  last-used/revocation state, and creation metadata;
- destructive revocation requires an explicit user confirmation and must refresh only the current
  project's credential state;
- client expiry validation improves feedback, but server validation remains authoritative;
- customer-facing credential screens must never expose internal milestone or patch identifiers.


## 18. Operational verification rules

M2.7 makes operability part of the release contract. Required rules:

- bootstrap and verification commands must be executable from the documented repository root;
- commands executed inside the API container use `/opt/venv/bin/python`, `/opt/venv/bin/ruff`, and
  `/opt/venv/bin/mypy`; do not run `uv run` inside the built API container;
- bootstrap may apply idempotent migrations/schema changes but must never delete persistent volumes;
- verify both `/api/v1/health/live/` and `/api/v1/health/ready/`; readiness failure is a release blocker;
- operational telemetry smoke tests must enter through the public authenticated OTLP boundary rather
  than inserting ClickHouse rows directly;
- persistence verification must always include the credential-derived `project_id`; never use an
  unscoped raw-telemetry query as an application/verification example;
- project API-key secrets must not be accepted as ordinary command-line arguments, printed, written to
  files, committed, or included in failure output; prefer a secure prompt/stdin for local tooling;
- verification may print safe identifiers such as project UUID, API-key public prefix, generated span
  name, and row counts;
- an OTLP 503 is a retryable durable-sink failure and must never be rewritten into success by tooling;
- M2.7 may improve scripts/docs/tests for the existing ingestion path but must not pull query APIs,
  telemetry explorers, dashboards, retention, alerting, billing, or other M3+ features forward.

## 19. Telemetry query rules

M3 telemetry reads must preserve the same tenant guarantees as ingestion. Required rules:

- resolve browser telemetry requests through the session-authenticated, membership-scoped project
  queryset before opening a ClickHouse client;
- never accept organization identity from query parameters, URL slugs, metric attributes, or other
  caller-controlled telemetry fields;
- every ClickHouse application query must include both `organization_id` and `project_id` predicates
  derived from the authorized project;
- unknown and foreign project UUIDs return the same not-found behavior and must not query ClickHouse;
- use typed ClickHouse query parameters for metric names, timestamps, service/environment filters, and
  all other caller-controlled values; dynamic SQL identifiers/filter expressions are not accepted;
- bound time ranges and row/catalog limits at the API boundary before sending a query to ClickHouse;
- use half-open `[start, end)` time windows to make adjacent requests composable;
- do not silently coerce histogram, exponential-histogram, or summary metrics into scalar values;
- raw numeric series preserve metric type, aggregation temporality, monotonicity, dimensions, and point
  attributes so later UI transformations can remain explicit;
- return dependency-unavailable behavior (HTTP 503) when ClickHouse cannot serve a query; do not return
  an empty data set that could be mistaken for a healthy result;
- close ClickHouse clients on both success and failure paths;
- telemetry query APIs are read-only; M3 must not introduce raw telemetry mutation endpoints;
- tests must cover viewer read access, foreign-project non-discovery, bounded validation, parameterized
  filtering, ClickHouse failure behavior, and at least one live project-isolation query.

## 20. Metrics explorer UI rules

M3.2 browser telemetry reads follow these rules:

- use only the session-authenticated M3.1 metrics APIs; frontend code must never connect to ClickHouse;
- include project UUID and every query-defining value in TanStack Query keys;
- remount/reset explorer-local selection and filter state when project context changes;
- keep time-range choices within the backend seven-day maximum and send explicit UTC start/end values;
- show non-scalar catalog entries honestly but do not enable them as scalar series;
- do not derive rate, delta, average, percentile, or histogram values in the browser without a defined
  server/product semantic contract;
- do not draw a connected line across points that may belong to different service/environment series;
- distinguish loading, empty, error, and truncated states; HTTP 503 is not an empty series;
- exact service/environment filter inputs are query values, not authorization inputs;
- render raw point attributes as text only; do not interpret arbitrary telemetry attributes as HTML;
- bound client table rendering even when the API returns thousands of points; the visualization may use
  the returned bounded response while the table shows a clearly labeled recent subset;
- frontend tests must prove real catalog/series rendering, non-scalar handling, exact filter propagation,
  and visible query-failure behavior.

## 21. Dashboard panel rules

M3.3 project dashboards must preserve the control-plane/data-plane separation:

- persist dashboard panel configuration in PostgreSQL, never raw telemetry values or ClickHouse result
  snapshots;
- scope every configuration list/create/delete operation through the authenticated user's project
  membership before touching panel rows;
- viewers may read dashboard configuration but owner/admin/editor roles alone may pin or remove panels;
- resolve a panel deletion by both `project_id` and `panel_id`; a globally known panel UUID must not
  allow cross-project mutation;
- keep the V1 project dashboard bounded to six panels so one browser view cannot fan out into an
  unbounded number of ClickHouse queries;
- prevent duplicate saved queries with the same project, metric, time range, service, and environment;
- pin only the existing bounded 1h/6h/24h/7d scalar-query contract; do not persist arbitrary SQL,
  attribute expressions, organization IDs, or caller-defined query code;
- dashboard telemetry reads must reuse the M3.1 metrics-series API rather than adding a browser-to-
  ClickHouse path or a second query implementation;
- dashboard query keys include project ID, panel identity/configuration, and explicit start/end values;
- keep each dashboard panel response bounded; M3.3 requests at most 500 points per panel;
- show ClickHouse/query failures as failures and empty numeric series as empty state; never substitute
  stale or fabricated values;
- latest/min/max displays are simple summaries of raw returned number points, not rate/delta/histogram
  semantics;
- panel removal requires explicit confirmation in the browser, while backend RBAC remains authoritative;
- frontend/backend tests must cover viewer read-only behavior, foreign-project non-discovery, panel
  scoping, duplicate/limit enforcement, pin propagation, real series rendering, empty state, and removal.

## 22. Operational verification rules

M3+ operational smoke tooling must follow the same trust boundaries as production code:

- send telemetry through the public OTLP endpoint; never satisfy an ingestion smoke by inserting rows
  directly into ClickHouse;
- derive tenant IDs from an authenticated project credential and scope every direct diagnostic query by
  both organization and project plus a unique smoke identifier;
- use typed ClickHouse parameters in operational diagnostics when values are dynamic;
- verify first-party reads through a normal CSRF/session-authenticated HTTP flow; direct ClickHouse
  persistence alone is not proof that the browser query boundary works;
- require the browser/session user to independently have membership in the project bound to the
  telemetry key; the key itself must not grant browser access;
- do not print, write, cache, or commit bearer keys or browser passwords; clear plaintext variables after
  use and prefer secure prompts;
- temporary dashboard configuration must be created through the normal API, clearly identified, and
  removed after verification; never delete unrelated user panels to make room for a smoke run;
- normal operational verification may recreate containers but must not delete persistent volumes;
- an operator confirmation may be used for the rendered browser surface, but automated API/persistence
  checks must pass first and failures must remain failures rather than being recorded as a successful
  smoke;
- operational closeout must finish with the complete `scripts/verify.ps1` gate and a clean repository;
- generated build state such as `*.tsbuildinfo` must remain untracked so verification itself does not
  produce milestone changes.

## 23. Log query and correlation rules

M4 log/trace work must preserve these rules:

- resolve the project through authenticated membership before opening ClickHouse;
- include authorized `organization_id` and `project_id` predicates in every log/span query;
- treat trace IDs, span IDs, service names, environments, severities, bodies, and attributes as data,
  never authorization inputs;
- bound log-search time windows and row limits before query execution;
- pass service/environment/severity/body/trace filters as typed ClickHouse parameters;
- do not accept arbitrary SQL, regex, attribute-expression languages, or dynamic query fragments in the
  initial log-search API;
- validate correlation IDs to their OpenTelemetry hexadecimal widths before querying;
- return the all-zero missing-ID storage sentinel as `null` rather than a navigable trace/span ID;
- preserve raw severity/body/resource/scope/log attributes; do not fabricate normalized messages or
  inferred correlation;
- return HTTP 503 for ClickHouse query failure and keep empty results distinct from dependency failure;
- close ClickHouse clients on success and failure paths;
- add indexes, projections, materialized views, or retention changes only from measured query needs or an
  explicit product/storage decision;
- tests must include foreign-project non-discovery, parameterization, query bounds, dependency failure,
  correlation-ID validation, and a live two-project isolation query.


## 24. Logs explorer UI rules

M4.2 browser log reads must preserve these rules:

- use only the session-authenticated M4.1 `/logs/search/` endpoint; frontend code never queries ClickHouse;
- include project UUID, explicit UTC start/end, selected result limit, and every applied filter in the
  TanStack Query key;
- remount/reset explorer-local state when project context changes;
- keep browser time ranges within the seven-day API maximum and row limits within `1..1000`;
- keep draft filter text separate from applied filters so typing does not create unbounded query traffic;
- treat service/environment/severity/body/trace controls as query data only, never authorization inputs;
- render log bodies and arbitrary telemetry attributes as escaped React text, never HTML;
- display trace/span IDs only when returned by the API and do not create trace navigation before M4.3;
- distinguish loading, healthy-empty, dependency/query failure, and truncated states;
- do not infer severity classes, message templates, missing spans, or cross-log relationships that the raw
  response does not provide;
- frontend tests must cover raw log rendering, bounded filter propagation, healthy empty state, visible
  truncation, and query failure behavior.

## 25. Trace lookup and correlation UI rules

M4.3 trace work must preserve these rules:

- exact trace lookup must resolve the session user's project membership before ClickHouse access;
- every span query includes both authorized `organization_id` and `project_id`; a trace ID never supplies
  tenant authority;
- validate trace IDs as non-zero 32-character hexadecimal identifiers before query execution;
- keep trace windows half-open, timezone-aware, and no longer than seven days; cap span responses at
  `1..1000` and expose truncation;
- pass trace IDs and timestamps as typed ClickHouse parameters; do not interpolate caller data into SQL;
- preserve raw span timing, parent IDs, status, attributes, trace state, events, links, flags, and dropped
  counts; normalize only all-zero missing-ID sentinels to `null`;
- return HTTP 503 for ClickHouse failure and keep a healthy empty trace distinct from dependency failure;
- the browser must use only the session-authenticated M4.3 endpoint and include project UUID, trace ID,
  explicit start/end, and limit-defining state in the TanStack Query key;
- log-to-trace links may be emitted only for a valid non-zero trace ID returned by the log API and should
  carry the originating bounded time window;
- never synthesize parent/child spans, critical paths, service relationships, or missing telemetry; label
  a referenced parent outside the bounded response as not returned;
- render arbitrary attributes plus event/link JSON as escaped text, never HTML;
- distinguish initial, loading, healthy-empty, query-error, and truncated browser states;
- tests must cover foreign-project non-discovery, parameterization, bounds, dependency failure, live
  two-project trace isolation, correlated navigation, raw parentage/timing, and missing-parent honesty.

## 26. M4 operational closeout rules

M4.4 verification must preserve all existing ingestion/query trust boundaries:

- generate correlated smoke telemetry with unique trace/span IDs and a unique run marker for every run;
- send both signals through the authenticated public `/v1/traces` and `/v1/logs` routes; never insert
  verification rows directly into ClickHouse;
- derive organization/project IDs only by authenticating the project telemetry credential, then scope
  every diagnostic ClickHouse query by both IDs plus exact smoke dimensions and a bounded UTC window;
- pass dynamic diagnostic values as typed ClickHouse parameters;
- keep the project telemetry key on secure prompt/stdin paths and never print it, write it to a file, or
  include it in browser URLs/output;
- require the browser/session user to independently resolve the key-bound project through normal
  membership APIs; machine credentials must never grant first-party browser access;
- verify the fresh row through the normal M4 log-search API and the fresh trace through the normal M4
  exact-trace API before requesting human browser confirmation;
- operational correlation checks must compare actual trace/span IDs, root/child parentage, status,
  service/environment, and unique smoke markers rather than accepting any recent telemetry row;
- browser confirmation must exercise the real Logs **Open trace** navigation, not a direct ClickHouse or
  debug-only screen;
- verification may rebuild/force-recreate containers but must preserve persistent volumes;
- skip switches are debugging conveniences only; final milestone acceptance runs Compose recreation,
  browser confirmation, and the complete repository release gate;
- generated TypeScript build-state files covered by `.gitignore` must not remain tracked or require a
  manual restore after every production build;
- M4.4 is a verification/documentation closeout and must not introduce new telemetry query semantics,
  persistence models, retention policy, or speculative ClickHouse optimization.

## 27. Alert rule control-plane rules

M5.1 alert configuration must preserve these rules:

- alert rules are project-owned PostgreSQL control-plane records; raw telemetry and evaluation samples
  remain in ClickHouse;
- resolve the route project through the authenticated user's memberships before any alert rule is read
  or mutated;
- viewers may read alert-rule configuration; owner/admin/editor memberships alone may create, update,
  enable/disable, or delete rules;
- scope detail mutation by both `project_id` and alert-rule ID so a known foreign rule UUID cannot cross
  project boundaries;
- metric name, exact service/environment filters, comparison operator, threshold, and time window are
  configuration data, never authorization inputs;
- keep the initial condition grammar explicit and typed: raw latest scalar point, bounded window, exact
  filters, and `gt`/`gte`/`lt`/`lte`; do not accept arbitrary SQL, expressions, functions, or JSON query
  programs;
- reject non-finite thresholds before persistence;
- rule creation/update must not query ClickHouse merely to validate that a metric currently exists;
- keep rule collections bounded; M5.1 allows at most 50 rules per project so later evaluation cannot
  inherit an unbounded fan-out by accident;
- rule names are unique within a project and concurrency-sensitive create/update checks must be guarded
  by database transactions/locking plus a database constraint;
- M5.1 does not claim firing state, alert history, evaluation cadence, incident semantics, or
  notification delivery; those require later M5 slices and their own tests.

## 28. Alert evaluation and current-state rules

M5.2 evaluation must preserve these rules:

- evaluate telemetry outside browser/API request handlers; rule reads and writes must not synchronously
  execute alert evaluation;
- derive `organization_id` and `project_id` from the persisted rule/project relationship, never from
  telemetry attributes, command arguments, or browser query data;
- keep evaluation windows bounded to the rule's existing 1h/6h/24h/7d choices and pass metric name,
  timestamps, service, and environment as typed ClickHouse parameters;
- evaluate only scalar `number_value` points and compare the unique newest raw point directly with the
  configured `gt`/`gte`/`lt`/`lte` comparator;
- do not choose an arbitrary row when multiple points share the newest timestamp; record a bounded
  `ambiguous_latest_point` error until the rule language defines explicit series/aggregation semantics;
- keep healthy no-data distinct from failures: no scalar point is `no_data`; ClickHouse failure,
  ambiguity, or non-finite observed values are `error`;
- persist only current alert state/operational timestamps in PostgreSQL; do not copy raw metric values or
  create unbounded evaluation history in the control plane;
- never persist dependency exception text; expose only bounded internal error codes;
- invalidate current state when evaluation-affecting rule configuration changes, using `pending` for
  enabled rules and `disabled` for disabled rules;
- do not hold PostgreSQL transactions/row locks across ClickHouse network I/O; snapshot rule version,
  query telemetry, then lock only while committing current state;
- reject stale writes when the rule changed, became disabled, or a newer evaluation already committed
  while the telemetry query was running;
- update `state_changed_at` only when status changes; repeated same-status evaluations update the
  evaluation timestamp without creating a synthetic transition;
- the M5.2 management command is a one-shot worker boundary, not permission to introduce an implicit
  scheduler, notification side effects, incidents, or retry framework before those contracts exist.

## 29. Alerts workspace rules

M5.3 browser work must preserve these rules:

- use only the existing project alert-rule list/create/detail/patch/delete API; do not create a frontend
  telemetry query or duplicate rule endpoint;
- include `projectId` in every alert-rule React Query key and remount project workspaces when tenant
  context changes;
- render only persisted `AlertRuleState`; do not derive firing/OK from browser-side metric queries or
  fabricate an observed value that M5.2 intentionally does not persist;
- owners/admins/editors may receive create/edit/enable-disable/delete controls; viewers may read rules
  and current state only; Django remains authoritative for every mutation;
- keep the browser rule grammar identical to the backend (`metric_name`, bounded window, exact optional
  service/environment, comparator, finite threshold, enabled); do not add expression builders, rates,
  aggregations, or histogram semantics in the UI alone;
- `Refresh state` may invalidate/re-fetch the alert-rule query only; no browser action may synchronously
  invoke the evaluator, open ClickHouse, or create an implicit evaluation cadence;
- show loading, empty, error, read-only, and unavailable-state conditions explicitly; do not report a
  dependency failure as no-data or healthy state;
- keep action errors visible and require confirmation before destructive rule deletion;
- M5.3 adds no notification channel, incident, alert history, scheduler framework, or telemetry schema
  change.

## 30. Alert notification and webhook rules

M5.4 notification work must preserve these rules:

- notification channels and delivery retry state are PostgreSQL control-plane/operational records; raw
  telemetry values remain in ClickHouse;
- resolve every browser/API channel request through authenticated project membership before reading or
  mutating channel rows; viewers read only, owner/admin/editor roles write;
- scope channel detail operations by both project and channel UUID so a known foreign channel ID cannot
  cross tenants;
- keep the initial channel type webhook-only and collections bounded to ten channels per project;
- treat endpoint URLs as sensitive write-only configuration: never return the full URL from read APIs,
  logs, command output, or delivery error state;
- require outbound hosts to pass the server egress allowlist, reject URL userinfo/fragments, disable
  redirects, and allow plaintext HTTP only through an explicit debug/operator setting;
- return the webhook signing secret only in the create response; do not persist or expose a plaintext
  copy through list/detail/delivery APIs;
- sign the exact canonical JSON body with the channel secret and a timestamp header; never include the
  deployment `DJANGO_SECRET_KEY` itself in payloads or headers;
- enqueue delivery rows only inside the committed alert-state transition transaction and only for
  non-firing -> firing or direct firing -> ok recovery; repeated firing/ok evaluations and error/no-data
  transitions must not create duplicate or invented notifications;
- keep external HTTP outside evaluation/API database transactions; the one-shot dispatcher owns network
  delivery;
- use a bounded lease when claiming deliveries so concurrent workers do not intentionally send the same
  row, and reject stale completion from a superseded lease;
- cap each delivery at three attempts with explicit backoff; retry only network/timeouts, HTTP 408/425/429,
  and 5xx, while redirects/other 3xx/4xx and disallowed endpoints fail terminally;
- never persist response bodies or exception strings; store only bounded error codes and numeric response
  status;
- disabling a channel prevents new transition rows and cancels still-pending work when encountered by the
  dispatcher; an already in-flight attempt may complete;
- M5.4 does not introduce a permanent scheduler, Celery/Dramatiq, incidents, arbitrary notification
  templates, email/Slack-specific integrations, or ClickHouse schema changes.
