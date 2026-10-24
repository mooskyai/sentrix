# Sentrix — Data Models and Persistence

## M6.4 span relationship query — candidate

Read existing `sentrix_spans.trace_id`, `span_id`, `parent_span_id`,
`service_name`, `environment` and `start_time`; every read is scoped to trusted
`organization_id` and `project_id`. A request-local hash map resolves only
same-trace parent IDs inside a bounded scanned window. No new table, schema,
index, PostgreSQL graph, or materialized relationship. The 10,000-span scan cap
and 1–500 edge response bound prevent unbounded in-process aggregation.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 reuses `Map(String, String) resource_attributes` on existing `sentrix_metrics`,
`sentrix_logs` and `sentrix_spans` tables. One query groups an ordered tuple/vector of supported
keys, preserving co-observation from the same telemetry resource; missing values are ignored. No
schema changes, migrations, projections, inventory cache or new indexes. Bounded window, typed
tenant predicates and query-level aggregation budgets are required.

## M6.1 service-catalog storage contract

No new tables or schema migrations. The API aggregates exact `service_name`/`environment` values across
`sentrix_metrics` and `sentrix_logs` using their `timestamp` columns and `sentrix_spans` using its
`start_time` column. The SQL groups in ClickHouse, scopes **each** branch to trusted
`organization_id`/`project_id` with typed UUID/time parameters, and returns counts/min/max observed
times within the half-open window. PostgreSQL stores no derived service catalog entries.

**Authority:** `backend/apps/**/models.py`, Django migrations, and `backend/apps/telemetry/clickhouse_schema.py` at the actual repository SHA. This is a curated V1 M1–M5 index, not a replacement for schema code.

## 1. Data ownership

| Storage | Owner | Content |
| --- | --- | --- |
| PostgreSQL 18 | Django control plane | auth users/sessions, organizations, memberships, projects, API keys, dashboard panels, alert rules/current state, webhook channels/delivery retry |
| ClickHouse 25.8 | telemetry data plane | `sentrix_metrics`, `sentrix_logs`, `sentrix_spans` raw records |
| Redis 8 | runtime/coordination | connectivity now; no mandatory alert scheduler/queue |

**Invariant:** No raw telemetry samples/history in PostgreSQL. Control-plane models may store rule configuration, state, operational delivery metadata, but not sampled metric values.

## 2. Relational entities and cardinality

```text
User (Django auth)
  +-- OrganizationMembership -- Organization 1--N Project
                                         Project 1--N ProjectApiKey
                                         Project 1--N ProjectDashboardPanel
                                         Project 1--N AlertRule 1--1 AlertRuleState
                                         Project 1--N NotificationChannel 1--N AlertNotificationDelivery
```

| Model | Key fields | Constraints / notes |
| --- | --- | --- |
| `Organization` | UUID id, unique slug, name, timestamps | global organization slug uniqueness |
| `OrganizationMembership` | UUID id, organization/user FKs, role | unique `(organization,user)`; owner/admin/editor/viewer |
| `Project` | UUID id, organization FK, slug/name, creator | unique `(organization,slug)` |
| `ProjectApiKey` | UUID id, project FK, 12-hex public prefix, hashed secret, JSON scopes, expiry/revocation/last-used | full credential returned once; `telemetry:write` |
| `ProjectDashboardPanel` | UUID id, project FK, title, metric_name, time_range, exact service/environment, position | unique `(project,metric_name,time_range,service_name,environment)`; cap 6 |
| `AlertRule` | UUID id, project FK, name, scalar metric configuration, comparator, threshold, enabled | unique `(project,name)`; cap 50 |
| `AlertRuleState` | rule OneToOne PK, status, evaluated/changed/source timestamps, bounded error_code | current status only; **no observed value** |
| `NotificationChannel` | UUID id, project FK, name, webhook type, endpoint URL, enabled, creator | unique `(project,name)`; cap 10; endpoint not returned by read serializers |
| `AlertNotificationDelivery` | UUID id, channel FK, alert_rule_id UUID snapshot, transition/event/payload/status, retry & lease fields | unique `(channel,alert_rule_id,event_type,state_changed_at)`; due index `(status,next_attempt_at)` |

`AlertNotificationDelivery.alert_rule_id` is a UUID snapshot, **not an FK**. The delivery payload is notification configuration/state, not raw metric data. Channel deletion cascades its delivery history; do not assume this is an immutable audit log.

## 3. ClickHouse telemetry schema v1

Three `MergeTree` tables partition by UTC month (`toYYYYMM(timestamp)` or spans' `start_time`). Every row stores server-derived `organization_id` and `project_id`, `schema_version`, `service_name`, `environment`, scope/resource attributes and signal-specific fields.

| Table | Sorting key | Core fields |
| --- | --- | --- |
| `sentrix_metrics` | `(organization_id,project_id,metric_name,timestamp)` | nanosecond timestamp, name/type/unit/temporality, nullable `number_value`, histogram/exponential/summary structures, attrs |
| `sentrix_logs` | `(organization_id,project_id,service_name,timestamp,trace_id)` | timestamp/observed_timestamp, severity, body/event, trace/span FixedString IDs, attrs |
| `sentrix_spans` | `(organization_id,project_id,service_name,start_time,trace_id)` | start/end/duration_ns, trace/span/parent IDs, kind/status, events/links JSON, attrs |

Telemetry models preserve shape distinctions. A histogram/summary is **not** a scalar point for the metrics explorer or alert threshold evaluator. Missing trace/span IDs use an all-zero fixed-width sentinel in ClickHouse; API normalization renders them `null`.

**No speculative** TTLs, secondary projections, preaggregation tables, materialized views, or schema migrations for M6 before query measurements.

## 4. Schema and migration workflow

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py migrate --noinput
docker compose exec -T api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
```

Migrations are under the respective Django app `migrations/` directories; ClickHouse schema is managed by a **separate** Django command. Never use `makemigrations` as a ClickHouse schema updater. Preserve volumes (`docker compose down`, never `down -v`) during normal maintenance.

## 5. Query safety and tenancy

All telemetry application reads resolve the authenticated session user's project membership **before** ClickHouse. Every query passes both org/project IDs as typed parameters along with bounded time/filter parameters. Direct diagnostics in smoke scripts must derive identity from the authenticated project key; resource attrs cannot elevate authority.

## 6. Updating this document

Every model/field/index/constraint/migration or ClickHouse DDL change requires updating this page, `ARCHITECTURE.md`, `API.md` if response contracts change, matching tests, and the implementation register in the same patch. Include a migration rollback/data-preservation plan when schema changes are not trivially reversible.

## M6 storage contract (planned; no migration approved)

M6.1 through M6.4 should **read** the existing tenant-keyed `sentrix_metrics`, `sentrix_logs`, and `sentrix_spans` ClickHouse tables; discovered service names/environments and host/Kubernetes dimensions are query-time interpretations of existing scalar columns and `resource_attributes`. A service inventory table, Django model, graph table, Redis materialization, ClickHouse index/TTL/projection or new schema version is **not** approved by M6 planning alone.

| Discovered concept | Existing data source | Identity caveat |
| --- | --- | --- |
| Observed service | `service_name`, `environment` in all three signal tables | Exact observed pair, scoped to project and time |
| Host or Kubernetes resource | `resource_attributes` map | Only recognized keys actually present; missing value is unknown |
| Service relationship | `sentrix_spans` trace/parent span IDs plus service identity | Both spans must exist in same authorized project and trace |

M6 query reviews must prove `organization_id` + `project_id` are enforced in **every** telemetry table read before aggregation/join, time bounds use half-open UTC intervals, external inputs are typed parameters, row counts are capped, and cross-service joins cannot bridge projects. Assess query performance on real workload before introducing schema optimizations. See `V1_M6_MILESTONE_TESTING.md`.
