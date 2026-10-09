# Sentrix Architecture

## 1. System goal

Sentrix is designed as a multi-tenant observability product covering metrics, logs, traces, dashboards, monitors, incidents, infrastructure, and integrations.

V1 intentionally builds the identity and tenancy foundation first. Telemetry ingestion comes after tenant and permission boundaries are stable.

## 2. Architectural principles

1. **Separate control plane from telemetry data plane.**
2. **Tenant isolation is enforced server-side.**
3. **Start as a modular monolith; split only workloads that need independent scaling.**
4. **Use OpenTelemetry as the primary future ingestion contract.**
5. **Choose storage by workload rather than forcing one database to do everything.**
6. **Prefer stateless HTTP services and independently scalable workers.**
7. **Make Sentrix itself observable from the beginning.**

## 3. Context diagram

```text
                       Browser
                          |
                          | HTTPS
                          v
                 +-----------------+
                 | React Web App   |
                 +--------+--------+
                          |
                          | /api/v1
                          v
                 +-----------------+
                 | Django API      |
                 | Control Plane   |
                 +--+-----------+--+
                    |           |
                    |           +--------------+
                    v                          v
             +-------------+             +-----------+
             | PostgreSQL  |             | Redis     |
             +-------------+             +-----------+

                 Future query boundary
                          |
                          v
                    +-----------+
                    | ClickHouse|
                    +-----------+
```

## 4. Future telemetry data plane

```text
Applications / Hosts / Kubernetes / Cloud Integrations
                         |
                         | OTLP / Prometheus / logs
                         v
              +------------------------+
              | OpenTelemetry Collector|
              +-----------+------------+
                          |
                          v
                  +---------------+
                  | Ingestion API |
                  +-------+-------+
                          |
                          v
                  +---------------+
                  | Stream Layer  |
                  | Redpanda/Kafka|
                  +---+-------+---+
                      |       |
        +-------------+       +--------------+
        v                                    v
 +--------------+                      +--------------+
 | Metric Worker|   ...                | Trace Worker |
 +------+-------+                      +------+-------+
        |                                     |
        +-----------------+-------------------+
                          v
                    +-----------+
                    | ClickHouse|
                    +-----+-----+
                          |
                          v
                    +-----------+
                    | Query API |
                    +-----+-----+
                          |
                          v
                      React UI
```

The stream layer is not required in the V1 starter. It is introduced when ingestion begins so write bursts can be decoupled from ClickHouse persistence and downstream processors.

## 5. V1 deployment units

### React web application

Responsibilities:

- login/logout UI
- organization/project selection
- platform navigation
- API calls
- user-visible authorization states

The React app is not an authorization boundary.

### Django API

Responsibilities:

- sessions/authentication
- organizations and memberships
- projects
- RBAC enforcement
- health/readiness
- future dashboard/alert/integration configuration

Django is the authoritative control-plane boundary.

### PostgreSQL

Stores durable relational control-plane state.

V1 examples:

```text
auth_user
organizations_organization
organizations_organizationmembership
projects_project
```

Future examples:

```text
dashboards
alert_rules
notification_channels
integrations
audit_events
subscriptions
```

### Redis

Used for ephemeral coordination. V1 readiness validates connectivity; later milestones can add cache, rate-limit state, locks, queues, and short-lived stream coordination.

### ClickHouse

V1 validates connectivity only. It is reserved for telemetry and analytical workloads.

Do not put user/session/organization truth in ClickHouse.

## 6. Tenant model

```text
User
  |
  +---- OrganizationMembership ---- Organization
                                      |
                                      +---- Project
                                      |
                                      +---- Project
```

A user can belong to multiple organizations. Membership carries the organization-level role.

Initial roles:

```text
OWNER
ADMIN
EDITOR
VIEWER
```

Role intent:

| Role | Manage org | Manage members | Create/update projects | Read projects |
| --- | --- | --- | --- | --- |
| Owner | Yes | Yes | Yes | Yes |
| Admin | Limited/Yes | Yes | Yes | Yes |
| Editor | No | No | Yes | Yes |
| Viewer | No | No | No | Yes |

V1 implements the reusable role model and project write boundary. Fine-grained permissions can be added without replacing membership.

## 7. Tenant query invariant

A project list is not:

```text
SELECT * FROM projects;
```

Conceptually it is:

```text
SELECT projects.*
FROM projects
JOIN memberships ON memberships.organization_id = projects.organization_id
WHERE memberships.user_id = :authenticated_user;
```

Object-detail routes use the same scoped queryset. This prevents insecure direct object reference bugs caused by guessing UUIDs.

## 8. Authentication

V1 browser authentication uses Django sessions.

Flow:

```text
Browser
  |
  | GET /auth/csrf/
  v
CSRF cookie
  |
  | POST /auth/login/ + X-CSRFToken
  v
Django authenticate()
  |
  v
Session cookie
  |
  | authenticated API requests
  v
/api/v1/...
```

Why session authentication first:

- first-party web application
- strong CSRF protections are built into Django
- no need to store bearer tokens in browser storage
- simple logout/invalidation semantics

Future agent/ingestion authentication uses scoped API keys or machine credentials, separate from browser sessions.

## 9. API boundary

The public application boundary starts at `/api/v1/`.

V1 routes:

```text
/api/v1/health/live/
/api/v1/health/ready/
/api/v1/auth/*
/api/v1/organizations/*
/api/v1/projects/*
```

Rules:

- Browser sends credentials only to the configured API origin.
- API serializes stable resource shapes.
- Views do not expose database internals.
- Tenant checks happen before data is returned.

## 10. Health model

### Liveness

`/health/live/` answers whether the Django process is running. It does not require downstream services.

### Readiness

`/health/ready/` checks whether the instance can serve normal application traffic by probing:

- PostgreSQL
- Redis
- ClickHouse

The endpoint returns HTTP `200` when dependencies are available and `503` when one or more required dependencies fail.

In later production deployments, readiness requirements may differ by deployment unit. For example, a control-plane API that does not execute telemetry queries may treat ClickHouse as a degraded dependency rather than a hard readiness dependency. That decision should be explicit.

## 11. Data ownership

| Data | Owner | Storage |
| --- | --- | --- |
| Users | Django | PostgreSQL |
| Organizations | Django | PostgreSQL |
| Memberships/RBAC | Django | PostgreSQL |
| Projects | Django | PostgreSQL |
| Dashboard definitions | Django | PostgreSQL |
| Alert definitions | Django | PostgreSQL |
| Integration configuration | Django | PostgreSQL |
| Metrics | Telemetry services | ClickHouse |
| Logs | Telemetry services | ClickHouse |
| Traces/spans | Telemetry services | ClickHouse |
| Cache/locks | Runtime services | Redis |

## 12. Telemetry schema direction

Later milestones should make tenant filtering physically useful, not only logically correct. Typical rows will include:

```text
organization_id
project_id
timestamp
service_name
environment
signal-specific fields
attributes
```

Every user query has a bounded tenant scope and time range.

ClickHouse table engines, partitioning, ordering keys, TTLs, projections, and materialized views will be chosen from measured query patterns rather than guessed during V1.

## 13. Background work

Do not run long-lived work inside request handlers.

Future asynchronous workloads include:

- alert evaluation
- notification delivery
- integration polling
- data rollups
- retention/cleanup coordination
- scheduled reports

A later milestone can introduce Celery/Dramatiq or purpose-built workers after the actual workload is known. Redis availability in V1 does not force a queue technology choice.

## 14. Repository architecture

The backend begins as a modular monolith:

```text
backend/apps/
  accounts/
  common/
  organizations/
  projects/
  dashboards/      future
  alerts/          future
  integrations/    future
```

This is intentional. Service boundaries will be introduced around scaling/failure domains, particularly ingestion and telemetry processing, instead of splitting CRUD domains into network services prematurely.

## 15. Security boundary

Trust order:

```text
Untrusted browser input
       |
       v
Authentication
       |
       v
Membership / role authorization
       |
       v
Validated serializer input
       |
       v
Domain operation
       |
       v
Database
```

Never reverse this by loading an arbitrary tenant object first and deciding later whether the user may see it.

## 16. Version 1 milestone evolution

### V1 M1

Control-plane foundation.

### V1 M2

OpenTelemetry ingestion gateway, machine API keys, ClickHouse telemetry schemas, ingestion metering.

### V1 M3

Metrics explorer and first dashboard panels.

### V1 M4

Logs and trace correlation.

### Later

Alert evaluation and notification dispatch.

Service catalog, Kubernetes/infrastructure views, incidents, integrations, usage-based plans, SSO, advanced analytics.

This sequence preserves a stable tenancy/security core while adding independently scalable telemetry capabilities.

V1 M2 is delivered in ordered parts. M2.1 introduces project-scoped API-key lifecycle only. Each
credential belongs to one project and therefore one organization. The full raw secret is shown only
when the key is created; PostgreSQL stores the public prefix, one-way secret hash, scope metadata,
optional expiry, last-use metadata, and revocation state.

The initial scope is deliberately narrow: `telemetry:write`. Browser sessions continue to protect
control-plane APIs. Machine credentials are not accepted as a global replacement for session auth.

## 17. Project workspace routing

The browser has a canonical project-context route:

```text
/orgs/:organizationSlug/projects/:projectSlug
/orgs/:organizationSlug/projects/:projectSlug/:section
```

This route is intentionally human-readable, but slugs are not security credentials. Workspace
resolution follows this order:

```text
Authenticated session
      |
      v
GET member organizations + member projects
      |
      v
Resolve URL slugs only inside that already-scoped result set
      |
      v
Render project workspace or unavailable state
```

Direct object reads and mutations still go through Django's membership-scoped project queryset. A
foreign UUID therefore remains inaccessible even if a caller knows it exactly.

The workspace navigation exposes `overview`, `metrics`, `logs`, `traces`, `dashboards`, `alerts`, and
`settings`. Overview and settings own real control-plane state. Telemetry sections keep stable routes
without inventing synthetic data while tenant-safe query APIs and explorers are still pending.

Organization/project switchers are also tenant-scoped. Changing organization selects only a project
already present in the authenticated user's project collection. If the selected organization has no
project, the UI returns to the control-plane overview where an authorized user can create one.

RBAC-aware frontend controls improve usability, but Django remains authoritative. Owner, admin, and
editor roles may receive project-write controls; viewer controls are read-only. Hiding a control is
never a substitute for backend authorization.

## 17. Frontend design system

Sentrix uses Tailwind CSS 4 as the styling engine through `@tailwindcss/vite`. The design system is
CSS-first rather than JavaScript-config-first: product tokens are declared with Tailwind's `@theme`
directive in `frontend/src/theme.css`, and semantic application classes in the global stylesheet
compose utilities with `@apply`.

The initial theme is **Sentrix Spectrum**. Its visual hierarchy intentionally favors dense operational
workflows: a compact 208px project sidebar, 52px top bar, reduced content/panel spacing, restrained
signal teal for active state and actions, violet for secondary signal emphasis, and separate semantic
colors for success, warning/read-only, and error states. Text uses softened off-white, readable muted,
and explicit disabled tokens so the dark theme remains legible without relying on glare or neon color.

Design tokens are presentation contracts only. Organization/project tenancy, RBAC, API scope, and
telemetry boundaries remain owned by the application/backend architecture and must never depend on
CSS state.


## 18. Machine authentication boundary

V1 M2.2 keeps browser and machine trust paths deliberately separate:

```text
Browser                         Collector / Agent
   |                                  |
   | Django session                   | Bearer project API key
   v                                  v
Control-plane API             ProjectApiKeyAuthentication
                                      |
                                      v
                              verify secret hash
                                      |
                              revoked / expiry check
                                      |
                                      v
                        ProjectApiKeyPrincipal
                         organization_id
                         project_id
                         api_key_id
                         scopes
                                      |
                                      v
                             scope permission
```

Machine authentication is opt-in per endpoint; it is not added to DRF's global authentication list.
A successful credential lookup derives tenant context from the persisted API-key relationship, so a
caller cannot switch organization or project by supplying identifiers in an ingestion payload.

The raw bearer value is never persisted or logged. Django's password hasher verifies the secret,
revoked and expired keys fail authentication, and `last_used_at` advances only after valid credential
authentication. Scope authorization occurs after authentication; a valid key can therefore be
recognized while still receiving HTTP 403 when it lacks an endpoint's required scope.

M2.2 does not create public ingestion routes. OTLP/HTTP protocol handling begins in M2.3.

## 19. OTLP/HTTP ingestion gateway

V1 M2.3 adds a dedicated telemetry protocol app and keeps the OTLP wire contract separate from the
control-plane API:

```text
Collector / SDK
      |
      | POST /v1/{metrics|logs|traces}
      | Authorization: Bearer sentrix_pk_...
      | application/x-protobuf
      v
Project API-key authentication
      |
      v
OTLP body-size / gzip boundary
      |
      v
Official Export*ServiceRequest protobuf decode
      |
      v
OtlpBatch(organization_id, project_id, api_key_id, signal, message)
      |
      v
Telemetry sink seam
```

The initial receiver supports binary OTLP protobuf plus `identity` and `gzip` encodings. The 64 MiB
default body limit is configurable through `OTLP_MAX_REQUEST_BYTES` and is enforced again after gzip
decompression. Malformed payloads are HTTP 400, oversized payloads are HTTP 413, unsupported media or
content encodings are HTTP 415, and authentication/scope failures remain 401/403. Error bodies use
`google.rpc.Status` when the request uses binary protobuf.

M2.3 intentionally has no durable telemetry sink. Non-empty valid batches therefore receive HTTP 503
rather than a false OTLP success acknowledgement. Empty OTLP requests may return the protocol-defined
success response because no telemetry can be lost. ClickHouse persistence begins in M2.4/M2.5.


## 20. ClickHouse telemetry schema

V1 M2.4 makes ClickHouse tenancy and signal shape explicit while keeping persistence disconnected from
the OTLP request path until M2.5.

```text
sentrix_metrics
  PARTITION BY toYYYYMM(timestamp)
  ORDER BY (organization_id, project_id, metric_name, timestamp)

sentrix_logs
  PARTITION BY toYYYYMM(timestamp)
  ORDER BY (organization_id, project_id, service_name, timestamp, trace_id)

sentrix_spans
  PARTITION BY toYYYYMM(start_time)
  ORDER BY (organization_id, project_id, service_name, start_time, trace_id)
```

All three tables use `MergeTree`, carry `schema_version = 1`, and start their physical sort keys with
organization/project identity. This makes tenant boundaries useful for pruning rather than merely
logical metadata.

The metric table is point-oriented and has explicit columns for number points, classic histograms,
exponential histograms, and summaries. The schema therefore does not pretend every OpenTelemetry
metric can be represented as one floating-point value. Log rows preserve severity/body plus trace and
span IDs. Span rows preserve trace/span/parent IDs, duration/status, attributes, and serialized event
and link payloads.

Resource and record attributes initially use `Map(String, String)`. Nested span events/links remain JSON
strings in M2.4 so the first storage contract does not invent unstable nested ClickHouse structures
before real query patterns exist.

There is deliberately no TTL in M2.4. Retention policy, codecs, projections, skip indexes, and
materialized views require measured ingestion/query behavior or an explicit product decision.

Schema lifecycle is independent of Django migrations. `manage.py clickhouse_schema` applies idempotent
`CREATE TABLE IF NOT EXISTS` statements; `manage.py clickhouse_schema --check` validates the live
column/type layout plus partition and sorting keys.

## 21. End-to-end telemetry persistence

V1 M2.5 activates the durable write path while retaining the M2.3 protocol boundary and M2.4 physical
schema unchanged:

```text
Collector / SDK
      |
      v
/v1/metrics | /v1/logs | /v1/traces
      |
      v
ProjectApiKeyPrincipal
 organization_id / project_id
      |
      v
Export*ServiceRequest protobuf
      |
      v
signal normalizer
      |
      +--> sentrix_metrics
      +--> sentrix_logs
      `--> sentrix_spans
      |
      v
successful ClickHouse insert
      |
      v
OTLP Export*ServiceResponse
```

Tenant identity is never derived from OTLP resource attributes. Every persisted row receives
`organization_id` and `project_id` from the authenticated project credential. Resource metadata only
supplies telemetry dimensions such as service name, environment, and arbitrary attribute maps.

Persistence is synchronous in M2.5 so the acknowledgement contract is unambiguous: a non-empty request
returns success only after ClickHouse accepts all rows produced for that signal batch. Connection or
insert failures are translated to retryable HTTP 503 responses. A later streaming architecture may
replace this synchronous boundary only when it can preserve the same durable-acceptance semantics.

Normalization remains separate from the HTTP view and from ClickHouse DDL. Metric rows retain their
family-specific shapes; logs retain trace/span correlation; spans retain parentage, status, events,
and links. OpenTelemetry integer nanosecond timestamps are converted to UTC `DateTime64` values for the
current Python/ClickHouse client boundary; duration remains explicitly stored in nanoseconds.

## 22. Project credential management UI

V1 M2.6 exposes project API-key lifecycle through the browser without weakening the separation between
session-authenticated control-plane actions and machine-authenticated telemetry ingestion:

```text
Project workspace /settings
        |
        | Django session + CSRF
        v
/api/v1/projects/{project_id}/api-keys/
        |
        +--> list safe metadata
        +--> create -> raw secret returned once
        `--> revoke
```

The settings route resolves organization/project slugs only inside the already tenant-scoped browser
workspace, then uses the immutable project UUID for control-plane requests. Backend membership/RBAC
checks remain authoritative. Viewer workspaces do not fetch project API-key metadata because the
control-plane endpoint intentionally requires project write authority.

The one-time create secret is a special client-side boundary. It must not enter TanStack Query caches,
local/session storage, URLs, analytics, or logs. The create request is therefore handled directly and
the raw credential is kept only in transient component state. Project changes remount the credential
panel so any undisclosed secret is dropped with the previous project context.

List state remains tenant-safe through a query key that includes the project UUID. Revoke and create
operations invalidate only that project's API-key query. The UI may show expiry, last-used, revocation,
scope, and prefix metadata because those values are already part of the safe control-plane response.


## 23. Operational verification boundary

V1 M2.7 does not add another product/data-plane capability. It closes the ingestion foundation by
proving the existing boundaries can be operated together from a clean local environment:

```text
bootstrap
   |
   +--> PostgreSQL migrations
   +--> ClickHouse schema apply/check
   +--> liveness/readiness
   |
   v
project settings -> one-time project API key
   |
   v
real OpenTelemetry OTLP/HTTP exporter
   |
   v
/v1/traces -> project API-key auth -> ClickHouse insert
   |
   v
tenant-scoped ClickHouse verification
```

Operational verification must use the same production-shaped contracts as normal ingestion. It must
not insert synthetic rows directly into ClickHouse, derive tenant identity from OTLP payloads, or
print/store the one-time bearer credential. The smoke exporter sends through the public OTLP route and
verifies persistence using the `project_id` derived from the authenticated credential.

The readiness endpoint remains the dependency-level operational signal: it checks PostgreSQL, Redis,
and ClickHouse and returns HTTP 503 when any dependency is unavailable. ClickHouse schema validation is
separate because dependency reachability alone does not prove the expected telemetry table contract.

M2.7 also makes the development release gate Compose-first. Commands executed inside the API container
use `/opt/venv/bin/...`; `uv run` is reserved for host-side development because running it inside the
built container can resynchronize `/opt/venv`. Persistent volumes are never deleted as part of normal
bootstrap or verification.

## 24. Metrics read/query boundary

V1 M3.1 introduces the first telemetry read path while preserving the control-plane/data-plane split:

```text
Authenticated browser session
        |
        v
project membership-scoped lookup in PostgreSQL
        |
        | authorized organization_id + project_id
        v
bounded metrics query service
        |
        v
ClickHouse sentrix_metrics
```

The browser supplies a project UUID as a resource locator, not tenant authority. Django first resolves
that UUID through `projects_for_user`; only the resulting persisted organization/project IDs are used in
ClickHouse predicates. Unknown and foreign project UUIDs therefore stop at the control-plane boundary
and never trigger telemetry reads.

M3.1 keeps read semantics deliberately narrow. Catalog queries expose metric shape metadata and recent
activity. Series queries return only scalar OpenTelemetry number points (`number_value`) and preserve
metric type, aggregation temporality, monotonicity, service/environment, and point attributes. The read
path does not average cumulative sums, derive rates, or flatten histogram/summary data because those
transformations require explicit metric semantics.

Every query has a bounded UTC time window and result limit. Values supplied by the client are passed to
ClickHouse as typed query parameters; only validated integer limits and fixed SQL fragments are composed
into SQL. ClickHouse errors become HTTP 503 without leaking connection or query internals.

M3.1 does not add telemetry Django models or copy raw telemetry into PostgreSQL. PostgreSQL continues to
own users, tenancy, projects, roles, and other control-plane state; ClickHouse remains the telemetry read
and write store.

## 25. Metrics explorer client boundary

V1 M3.2 connects the existing project Metrics route to the M3.1 read contract without creating a second
telemetry-query path:

```text
Project workspace /metrics
        |
        | project UUID resolved from tenant-scoped workspace
        v
TanStack Query catalog request
        |
        v
select scalar metric + bounded window + exact filters
        |
        v
TanStack Query series request
        |
        v
observed-point plot + point table
```

The browser never queries ClickHouse directly and never derives tenant identity from organization/project
slugs. Workspace resolution still happens inside the session-scoped organization/project collections,
then the immutable project UUID is passed to the same Django query API whose membership check is the
security boundary.

Explorer query keys include project UUID, explicit start/end timestamps, selected metric, and applied
service/environment filters. Project changes remount the explorer so selection/filter state cannot bleed
between tenants. Query errors remain visible errors; the client must not reinterpret HTTP 503 as an empty
series.

The first visualization is an observed-point plot rather than a connected trend line. A single response
may contain more than one service/environment combination, so connecting points could imply continuity
between distinct series. The table exposes the raw dimensions and point attributes needed to understand
that context.

M3.2 performs no metric arithmetic. Monotonic/cumulative sums remain raw values; histograms, exponential
histograms, and summaries remain catalog-visible but scalar-unselectable. Rate functions, aggregation,
percentiles, grouping, and dashboard reuse remain later M3 work with explicit semantics.

## 26. Project dashboard configuration boundary

V1 M3.3 adds the first persisted dashboard configuration without moving telemetry into PostgreSQL:

```text
Metrics explorer
      |
      | owner/admin/editor pins selected scalar query
      v
PostgreSQL ProjectDashboardPanel
      |  metric_name / time_range / exact filters / position
      |
      v
Project workspace /dashboards
      |
      | session-authenticated project membership
      v
M3.1 /metrics/series/ query boundary
      |
      v
ClickHouse sentrix_metrics
```

`ProjectDashboardPanel` is control-plane state. It belongs to exactly one project and stores no observed
values, raw attributes, rollups, or copies of ClickHouse rows. The V1 dashboard surface is intentionally
single-project/single-dashboard with at most six panels. This bounds browser fan-out while query
semantics are still narrow.

Any project member may list configured panels. Owner/admin/editor memberships may create and remove panel
configuration; viewer memberships remain read-only. The project is resolved through the same
membership-scoped Django queryset before panel configuration is read or mutated, and a panel ID is always
resolved together with its route project so cross-project deletion cannot occur.

Pinning is deliberately constrained to scalar queries already proven by the Metrics explorer: metric
name, one of the 1h/6h/24h/7d ranges, and optional exact service/environment filters. The backend does
not open ClickHouse while creating dashboard configuration. On render, each panel calls the existing
metrics-series API, which performs the tenant authorization and ClickHouse query. This keeps dashboard
configuration and telemetry storage independent.

Dashboard panels use raw returned gauge/sum number points. Latest/min/max are presentation summaries of
the bounded response, not new persisted aggregations or semantic transformations. M3.3 introduces no
counter-rate function, histogram flattening, percentile computation, materialized view, or dashboard-
specific telemetry API.

## 27. M3 operational verification boundary

M3.4 verifies the complete read path without introducing another application data path:

```text
project telemetry key
      |
      v
public OTLP/HTTP /v1/metrics
      |
      v
ClickHouse sentrix_metrics
      |
      +--> project-scoped durable persistence check
      |
normal browser session + membership
      |
      v
M3.1 catalog / numeric-series APIs
      |
      +--> Metrics explorer
      |
      `--> temporary ProjectDashboardPanel --> Dashboards
```

The OTLP smoke derives organization/project identity by authenticating the existing project key. Its
ClickHouse diagnostic uses both IDs, the unique metric name, exact service/environment, and a narrow UTC
window; it does not perform an unscoped telemetry scan. That diagnostic proves durable ingestion, while
the subsequent session-authenticated catalog/series requests independently prove the application read
boundary.

Dashboard verification intentionally uses ordinary PostgreSQL control-plane configuration. The closeout
creates one temporary panel through the public project API, asks the operator to confirm the fresh metric
in the real Metrics and Dashboards routes, and then removes only that temporary panel. No telemetry rows
are deleted or rewritten by verification.

`verify-m3.ps1` recreates application containers from the current repository but never removes persistent
volumes. It delegates the final static/test/build checks to `verify.ps1`; M3 operational verification is
therefore an end-to-end runtime proof layered on top of, not a replacement for, the normal release gate.

## 28. Logs read/query boundary

V1 M4.1 extends the proven project-scoped telemetry read pattern to `sentrix_logs`:

```text
Authenticated browser session
        |
        v
projects_for_user membership-scoped lookup
        |
        | authorized organization_id + project_id
        v
bounded log-search API
        |
        v
ClickHouse sentrix_logs
```

A trace ID, span ID, service name, body string, severity, or arbitrary telemetry attribute is data to
filter or display; none of it establishes tenant authority. Django resolves the route project first, and
every ClickHouse query includes both organization and project predicates derived from that object.
Unknown/foreign project UUIDs therefore stop before the data plane is opened.

M4.1 deliberately uses a narrow search grammar: bounded UTC time, exact service/environment, minimum
OpenTelemetry severity number, bounded case-insensitive body substring, and an exact validated trace ID.
Dynamic values are ClickHouse parameters. The only SQL assembled by application code is fixed query
structure plus a validated integer row limit. Arbitrary SQL, regex, attribute-expression languages, and
user-provided query fragments remain out of scope.

Log responses preserve resource, instrumentation-scope, and record attributes alongside severity/body
and correlation IDs. The write schema represents missing trace/span IDs with all-zero fixed-width values;
the query boundary converts those sentinels to `null` so later UI code cannot mistake them for valid
correlation targets. M4.3 may follow non-zero trace IDs only after independently applying the same
project authorization to span queries.

The first implementation queries the existing tenant-first ClickHouse ordering rather than adding
indexes, projections, materialized views, or retention changes before measured log-search behavior
exists. Query windows and row counts are bounded to keep that initial contract operationally safe.


## 29. Logs explorer client boundary

V1 M4.2 connects the existing Logs route to M4.1 without adding a browser-to-ClickHouse path:

```text
Project workspace /logs
        |
        | immutable project UUID from tenant-scoped workspace
        v
TanStack Query /logs/search/
        |
        | bounded UTC window + row limit + applied filters
        v
M4.1 Django membership boundary
        |
        v
ClickHouse sentrix_logs
```

The explorer keeps draft filter input separate from applied query state. Service, environment, severity,
body substring, and trace ID therefore do not trigger queries while the operator is typing. Applying or
clearing filters advances the bounded window anchor and changes a query key containing project UUID,
start/end, row limit, and every applied filter. Project changes remount the explorer.

The UI renders raw response fields rather than normalizing log bodies or inferring missing correlation.
Trace/span IDs are text in M4.2, including an explicit absent state for `null`; trace navigation waits for
M4.3 so following an identifier cannot bypass the future project-scoped span authorization boundary.
HTTP/query failures remain visible failures, healthy empty results remain empty states, and a truncated
response warns that the visible rows are incomplete.

## 30. Trace read and correlation boundary

V1 M4.3 adds exact trace lookup without treating correlation identifiers as authority:

```text
Logs explorer                         Traces workspace
     |                                     |
     | trace_id + bounded start/end        | manual trace_id + bounded start/end
     `------------------+------------------'
                        |
                        v
        Django membership-scoped project lookup
                        |
                        | authorized organization_id + project_id
                        v
           /traces/{trace_id}/ read boundary
                        |
                        v
                ClickHouse sentrix_spans
```

The route trace ID is data. Django resolves the project first, validates the ID and bounded window, then
passes organization ID, project ID, trace ID, and timestamps as typed ClickHouse parameters. A caller who
knows another tenant's trace ID still receives no access because foreign project routes stop at the
control plane and an authorized local-project lookup can only query that local tenant predicate.

The initial trace contract is exact-ID detail, not an unbounded trace catalog. It reads at most 1,001 rows
to return a maximum of 1,000 spans with explicit truncation. The existing `sentrix_spans` tenant-first
schema remains unchanged; M4.3 does not add an index/projection before measured query behavior warrants
one.

Span responses preserve stored parent IDs, start/end time, duration, kind/status, attributes, events,
links, flags, and dropped counts. All-zero fixed-width parent/span sentinels become `null`. The browser
may summarize returned span/service counts and format durations, but it must not invent a missing parent,
critical path, or cross-trace relationship. Log navigation carries the originating log query window so a
correlated trace is searched in the same bounded temporal context.
