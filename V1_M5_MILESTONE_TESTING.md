# Sentrix V1 M5 — Alerting Test and Acceptance Plan

## 1. Gate philosophy

Alerting can create external side effects later in M5, so each slice must prove tenant scope and explicit
semantics before background evaluation or notification delivery is allowed.

M5.1 is control-plane only. Its acceptance must not depend on direct ClickHouse inserts or fabricated
alert state.

## 2. M5.1 automated matrix

### AR-001 — Viewer read access

A viewer membership can list and read alert-rule configuration for its project.

### AR-002 — Writer lifecycle

Owner/admin/editor memberships can create, patch, enable/disable, and delete project alert rules.

### AR-003 — Foreign project non-discovery

A user using another tenant's project UUID receives `404`.

### AR-004 — Rule/project scoping

Knowing an alert-rule UUID does not permit reading or mutating it through another project route.

### AR-005 — Typed condition validation

Validate metric name, bounded time range, comparator, exact service/environment filters, enabled state,
and a finite numeric threshold. Reject unsupported comparators/ranges and NaN/infinite thresholds.

### AR-006 — Duplicate rule name

A project cannot contain two rules with the same name. The API returns a validation error and leaves one
record.

### AR-007 — Bounded rule collection

A project cannot exceed 50 alert rules. The create service uses project-level transactional locking so
concurrent writers cannot independently pass the same count check.

### AR-008 — Partial update honesty

PATCH changes only supplied fields. Disabling a rule or changing a threshold must not silently rewrite
its metric/filter/comparator configuration.

### AR-009 — Control-plane separation

Rule CRUD persists only PostgreSQL configuration. M5.1 does not query ClickHouse, create evaluation
state, or write telemetry copies.

### AR-010 — Regression gate

All M1-M4 backend/frontend/infrastructure tests and the normal repository release gate remain green.

## 3. Focused M5.1 checks

```powershell
docker compose exec api /opt/venv/bin/python -m pytest apps/alerts/tests/test_api.py -v

docker compose exec api /opt/venv/bin/ruff check apps/alerts
docker compose exec api /opt/venv/bin/ruff format --check apps/alerts
docker compose exec api /opt/venv/bin/mypy apps/alerts

docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
```

Then run:

```powershell
./scripts/verify.ps1
```

## 4. Manual API smoke

Using an owner/admin/editor browser session:

1. create one rule for a scalar metric;
2. list rules and confirm the rule is returned under the route project;
3. patch only `threshold` and `enabled` and confirm other condition fields remain unchanged;
4. sign in as a viewer and confirm read succeeds while create/patch/delete receive `403`;
5. attempt the project/rule UUID through an unrelated membership and confirm `404`;
6. delete the rule and confirm it no longer appears.

Do not treat a stored rule as an active alert. M5.1 has no evaluator or firing state.

## 5. M5.1 stop condition

M5.1 is complete only after the focused tests, migration checks, manual CRUD/RBAC smoke, full release
gate, commit, push, and a clean:

```text
## main...origin/main
```

Only then may M5.2 metric evaluation and alert state begin.

## 6. M5.2 automated matrix

### AE-001 — Initial/backfilled state

Existing rules receive a state row during migration. New enabled rules start `pending`; disabled rules
start `disabled`.

### AE-002 — Tenant-scoped metric query

Evaluator arguments use the rule project's persisted organization/project IDs plus the configured metric,
window, and exact service/environment filters.

### AE-003 — Comparator boundaries

`gt`, `gte`, `lt`, and `lte` are tested at boundary values without implicit epsilon or coercion.

### AE-004 — No-data honesty

A healthy query with no scalar point sets `no_data`. It must not be reported as `ok`.

### AE-005 — Dependency/error honesty

ClickHouse failures, ambiguous equal-latest timestamps, and non-finite observed values set `error` with a
bounded code. Exception text is not persisted.

### AE-006 — State transitions

`state_changed_at` changes only when status changes; `evaluated_at` advances on evaluation attempts
including `no_data` and `error`.

### AE-007 — Configuration invalidation

Changes to metric/window/filter/comparator/threshold reset enabled rules to `pending`. Disabling produces
`disabled` without querying ClickHouse.

### AE-008 — Stale-write protection

If a rule changes while an evaluation query is in flight, the stale result is skipped and cannot
overwrite the state produced by the newer configuration. An older overlapping evaluation also cannot
overwrite a state already persisted for a newer evaluation timestamp.

### AE-009 — Current-state API

Project rule list/detail responses expose only persisted current state and do not trigger ClickHouse
queries.

### AE-010 — Worker boundary

`manage.py evaluate_alerts` evaluates enabled rules outside HTTP request handlers, supports optional
project scoping, and exits non-zero when any rule ends in `error`.

### AE-011 — Latest-point query contract

The ClickHouse helper uses typed organization/project/metric/time/filter parameters, numeric points only,
newest-first selection, and explicitly rejects a tie at the newest timestamp.

### AE-012 — Regression gate

All M1-M5.1 tests plus the normal backend/frontend/schema/build gates remain green.

## 7. Focused M5.2 checks

```powershell
docker compose exec api /opt/venv/bin/python -m pytest `
  apps/alerts/tests/test_api.py `
  apps/alerts/tests/test_evaluation.py -v

docker compose exec api /opt/venv/bin/ruff check apps/alerts apps/telemetry/metrics_query.py
docker compose exec api /opt/venv/bin/ruff format --check apps/alerts apps/telemetry/metrics_query.py
docker compose exec api /opt/venv/bin/mypy apps/alerts apps/telemetry/metrics_query.py

docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
```

Then run the complete release gate:

```powershell
./scripts/verify.ps1
```

## 8. Manual M5.2 smoke

Use an existing project/rule and run the one-shot evaluator from the repository stack:

```powershell
docker compose exec api /opt/venv/bin/python manage.py evaluate_alerts --project-id <project-uuid>
```

Then read the rule through its existing project API and confirm the nested `state` reflects the persisted
result. Do not expect the Alerts workspace to render it yet; M5.3 owns the browser UI.

## 9. M5.2 stop condition

M5.2 is complete only after focused evaluator/state tests, migration checks, management-command smoke,
the full release gate, commit, push, and a clean:

```text
## main...origin/main
```

Only then may M5.3 Alerts workspace work begin.

## 10. M5.3 automated matrix

### AU-001 — Project-scoped state read

The Alerts workspace loads the current project's alert-rule collection and renders persisted current
state, timestamps, exact filters, comparator, threshold, and enabled state. It does not issue metric
queries.

### AU-002 — Viewer read-only behavior

Viewer access may read rules/state but receives no create/edit/enable-disable/delete controls.

### AU-003 — Writer create

Owner/admin/editor UI submits the complete typed scalar rule shape to the project-scoped create API.

### AU-004 — Writer edit

Editing a rule loads its current typed condition into the form and PATCHes the existing project/rule
endpoint. The browser does not synthesize evaluation state after the edit.

### AU-005 — Enable/disable

Enable/disable uses PATCH with only `enabled`; returned/persisted state is re-fetched from the backend.

### AU-006 — Delete confirmation

Deletion requires explicit browser confirmation before calling the project/rule delete endpoint.

### AU-007 — Current-state honesty

`pending`, `ok`, `firing`, `no_data`, `error`, and `disabled` are rendered as persisted. Missing state is
shown explicitly as unavailable. No raw metric value/history is invented.

### AU-008 — Refresh boundary

`Refresh state` only invalidates/re-fetches the project alert-rule query. No evaluator or telemetry query
API is invoked by the browser.

### AU-009 — UI failure states

Rule list loading/error/empty states and mutation errors remain distinct and visible.

### AU-010 — Regression gate

All backend M1-M5.2 tests, frontend tests, lint/typecheck/build, migration drift, and ClickHouse schema
checks remain green.

## 11. Focused M5.3 checks

```powershell
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm run test -- --run src/components/AlertsWorkspace.test.tsx
```

Then run the complete release gate:

```powershell
./scripts/verify.ps1
```

## 12. Manual M5.3 browser smoke

Using a writable project session:

1. open the project Alerts workspace and create a scalar threshold rule;
2. confirm the rule appears with its backend-provided current state;
3. edit the threshold and confirm the state becomes `pending` until the evaluator runs;
4. run `manage.py evaluate_alerts --project-id <project-uuid>` outside the browser and use `Refresh state`;
5. confirm the new persisted state appears without a browser telemetry query;
6. disable then enable the rule and confirm the backend state changes to `disabled`/`pending`;
7. delete the rule only after confirmation;
8. repeat as a viewer and confirm rule/state read succeeds while mutation controls are absent.

## 13. M5.3 stop condition

M5.3 is complete only after focused frontend tests, manual browser CRUD/state smoke, the full release gate,
commit, push, and a clean:

```text
## main...origin/main
```

Only then may M5.4 notification channels and dispatch begin.
