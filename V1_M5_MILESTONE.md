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

## 7. M5.2 evaluation-state contract

M5.2 adds one current `AlertRuleState` row per alert rule. It is control-plane state, not an evaluation
history table and not a copy of metric samples. The persisted state is:

```text
pending | ok | firing | no_data | error | disabled
```

The state records evaluation time, state-transition time, the source point timestamp when one uniquely
exists, and a bounded internal error code. The numeric telemetry value itself remains in ClickHouse.

Alert-rule list/detail responses now include this current state. No request handler evaluates telemetry;
HTTP reads only return persisted configuration/state.

## 8. M5.2 evaluation semantics

An enabled rule is evaluated against the half-open configured window ending at one evaluation timestamp.
The evaluator queries `sentrix_metrics` with organization/project IDs derived from the persisted rule
relationship, the rule metric name, and its exact optional service/environment filters.

Only `number_value` rows participate. The newest timestamp is selected. If no numeric point exists, the
state becomes `no_data`. If exactly one latest point exists, its raw value is compared directly with the
configured comparator and threshold. No rate, delta, average, percentile, histogram coercion, or other
aggregation is introduced.

If multiple numeric points share the newest timestamp, M5.2 does not choose an arbitrary series. The
state becomes `error` with `ambiguous_latest_point`; a later rule language may add explicit series or
aggregation semantics. Non-finite observed values also become `error`. ClickHouse/query failures become
`error`, never `no_data`.

Configuration changes that affect evaluation reset enabled rules to `pending`; disabling a rule makes
its state `disabled`. Evaluation snapshots the rule's `updated_at` before querying and refuses to persist
a stale result if the rule changes while the ClickHouse query is in flight. An older overlapping
evaluation also cannot overwrite a state already persisted by a newer evaluation timestamp.

## 9. M5.2 worker boundary

Evaluation runs outside HTTP request handlers through:

```powershell
docker compose exec api /opt/venv/bin/python manage.py evaluate_alerts
```

For a scoped operational/debug run:

```powershell
docker compose exec api /opt/venv/bin/python manage.py evaluate_alerts --project-id <project-uuid>
```

The command is a one-shot worker entrypoint suitable for an external scheduler. M5.2 deliberately does
not introduce Celery, Dramatiq, a cron container, or a permanent cadence before notification/retry
requirements are defined. It evaluates all eligible rules, persists current states, and exits non-zero
when one or more rules end in `error`.

## 10. M5.2 acceptance

M5.2 is green only when:

- every rule has/backfills a current state row and new rules start `pending` or `disabled`;
- list/detail APIs expose persisted current state without triggering evaluation;
- evaluator queries are always organization/project scoped from persisted relationships;
- windows and exact service/environment filters match the rule configuration;
- comparator boundaries are covered explicitly;
- no numeric point becomes `no_data`, while dependency/ambiguity/non-finite failures become `error`;
- equal newest timestamps are never resolved by an invented aggregation or arbitrary row choice;
- state transition time changes only when status changes;
- evaluation-affecting configuration changes invalidate prior state;
- stale in-flight results cannot overwrite state after a concurrent rule change or newer evaluation;
- a one-shot management command provides the non-request evaluation entrypoint;
- no alert history, incidents, notifications, scheduler dependency, or ClickHouse schema change is added;
- focused tests, migration drift checks, and the complete repository release gate pass;
- documentation remains synchronized.

## 11. Explicitly out of scope for M5.2

- browser Alerts management/state UI (M5.3);
- notification channels or delivery (M5.4);
- alert/evaluation history or incidents;
- periodic scheduler infrastructure;
- hysteresis, debounce, `for` duration, recovery delays, or silencing;
- aggregation across multiple simultaneous series;
- rates, deltas, percentiles, histogram alerting, logs, or trace alert rules;
- ClickHouse index/projection/materialized-view/TTL changes.

M5.3 must not begin until M5.2 is green, committed, pushed, and `main` is aligned with `origin/main`.
