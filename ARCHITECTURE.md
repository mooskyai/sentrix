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
