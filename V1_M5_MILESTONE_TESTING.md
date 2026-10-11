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
