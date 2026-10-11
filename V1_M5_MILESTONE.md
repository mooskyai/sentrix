# Sentrix V1 M5 — Alerting

## 1. Goal

V1 M5 adds project-scoped alerting on top of the telemetry ingestion/query boundaries proven by M2-M4.
The milestone starts with typed control-plane rule configuration, then adds evaluation state, a real
Alerts workspace, notification delivery, and an operational closeout.

Alerting must not weaken existing ownership boundaries:

- Django/PostgreSQL owns alert rules, notification configuration, and other control-plane state;
- ClickHouse remains the source of raw telemetry;
- a project route UUID is a locator, never tenant authority;
- evaluators derive organization/project identity from persisted project relationships;
- browser actions remain session-authenticated and membership scoped.

## 2. Ordered delivery

### M5.1 — Project alert-rule control-plane foundation

Deliver a bounded PostgreSQL model and session-authenticated project API for metric threshold rules.
This slice stores configuration only and does not evaluate telemetry.

### M5.2 — Metric evaluation and alert state

Evaluate enabled rules against the existing tenant-scoped scalar metric query semantics, persist current
control-plane state, make no-data explicit, and keep evaluation work outside request handlers.

### M5.3 — Alerts workspace

Replace the Alerts placeholder with project-scoped rule management and current-state UI backed only by
the M5 APIs.

### M5.4 — Notification channels and dispatch

Add an explicit notification-channel control plane and dispatch only on defined alert-state transitions.
Secrets and delivery retries must have their own security/failure contract.

### M5.5 — Operational verification and closeout

Exercise real OTLP metric ingestion through alert evaluation and notification test delivery, verify
tenant isolation/state transitions, run the browser flow, and finish with the complete release gate.

## 3. M5.1 API contract

```text
GET   /api/v1/projects/{project_id}/alert-rules/
POST  /api/v1/projects/{project_id}/alert-rules/
GET   /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
PATCH /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
DELETE /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
```

Any authenticated project member may read alert rules. Owner/admin/editor memberships may create,
update, enable/disable, and delete them. Unknown or foreign project UUIDs return `404` through the same
membership-scoped project selector used by the existing control plane.

## 4. Initial rule shape

M5.1 supports metric threshold configuration only:

```text
name          unique within project
metric_name   raw scalar metric name
time_range    1h | 6h | 24h | 7d
service_name  optional exact filter
environment   optional exact filter
comparator    gt | gte | lt | lte
threshold     finite number
enabled       boolean
```

The intended M5.2 condition is deliberately simple: locate the latest raw scalar point inside the
configured bounded window/exact filters and compare that value to the threshold. M5.1 stores that intent
but performs no ClickHouse read and exposes no firing state yet.

A project may hold at most 50 rules in the initial V1 control plane. This hard bound prevents M5.2 from
inheriting unbounded evaluation fan-out. It is a V1 operational contract, not a long-term pricing limit.

## 5. M5.1 acceptance

M5.1 is green only when:

- viewer membership may list/read local-project rules;
- owner/admin/editor membership may create, patch, enable/disable, and delete rules;
- a foreign project UUID returns `404`;
- a rule ID is always resolved together with its route project;
- metric/filter/threshold fields cannot override tenant identity;
- non-finite thresholds are rejected before persistence;
- rule names are unique within a project;
- the 50-rule project cap is enforced transactionally;
- create/update paths are protected against concurrent duplicate/cap races with project locking and a
  database uniqueness constraint;
- no alert-rule request opens ClickHouse or stores raw telemetry in PostgreSQL;
- a Django migration is included for the new control-plane schema;
- focused tests, migration drift check, and the full repository release gate pass;
- README, architecture, coding, milestone, and testing documentation agree with the implementation.

## 6. Explicitly out of scope for M5.1

- background evaluation;
- current firing/OK/no-data state;
- alert history/incidents;
- notification channels or delivery;
- rates, deltas, averages, percentiles, histogram coercion, or arbitrary expressions;
- log/trace alert rules;
- arbitrary SQL, user-provided query languages, or dynamic Python;
- Alerts workspace UI;
- ClickHouse schema/index/TTL changes.

M5.2 must not begin until M5.1 is green, committed, pushed, and `main` is aligned with `origin/main`.
