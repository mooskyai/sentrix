# Sentrix V1 M3 Testing — Metrics Explorer and First Dashboard Panels

## 1. Testing principle

M3 testing must prove telemetry reads are both semantically honest and tenant safe. A chart rendering is
not evidence of a correct query boundary; authorization, ClickHouse predicates, query bounds, failure
behavior, and real persisted telemetry must be verified independently.

## 2. M3.1 automated matrix

### MQ-001 — Viewer project read

Given a viewer membership, the metrics catalog endpoint returns HTTP 200 for that viewer's project.
Read-only RBAC does not block observability reads.

### MQ-002 — Foreign project non-discovery

Given a user from another organization and an exact foreign project UUID, catalog/series returns `404`
and the ClickHouse client is never opened.

### MQ-003 — Tenant predicates

Every application query includes authorized `organization_id` and `project_id` predicates. Tests assert
those parameter values come from the resolved Django project.

### MQ-004 — Query value parameterization

Metric name, timestamps, service name, and environment are typed ClickHouse parameters. Caller strings
must never be concatenated into SQL.

### MQ-005 — Time-window validation

Verify:

- timezone-aware RFC3339 timestamps are accepted;
- naive/invalid timestamps are rejected;
- `start >= end` is rejected;
- windows longer than seven days are rejected;
- omitted timestamps use the one-hour default.

### MQ-006 — Result bounds

Verify catalog limit `1..500` and series limit `1..5000`. Series requests read at most `limit + 1`
rows so the response can report truncation without an unbounded count query.

### MQ-007 — Metric-shape honesty

Catalog metadata may list gauge, sum, histogram, exponential-histogram, and summary types. The M3.1
series endpoint returns only rows with `number_value`; tests must not flatten histogram/summary state.

### MQ-008 — Dependency failure

A ClickHouse query failure returns HTTP `503`, does not leak dependency internals, and closes the client.

### MQ-009 — Live ClickHouse project isolation

Ingest the same uniquely named metric into two projects using two real project API keys. Query through a
session belonging to project A and prove only project A's value is returned. Querying project B with the
same session must return `404`.

### MQ-010 — Regression gate

M3.1 must keep all M2 tests and quality checks green.

## 3. M3.1 release gate

Run from the repository root with the Compose stack available:

```powershell
./scripts/verify.ps1
```

The expected gate remains:

```text
Backend
  pytest
  ruff check
  ruff format --check
  mypy
  Django system check
  makemigrations --check --dry-run
  ClickHouse schema --check

Frontend
  lint
  typecheck
  tests
  production build

Repository
  docker compose config --quiet
  git diff --check
```

After the gate:

```powershell
git status --short
git diff --stat
git diff --check
```

Do not commit M3.1 if any check is red.

## 4. Manual API smoke

After sending real metrics to a project, authenticate in the browser/session context and verify the
project's catalog/series endpoints. Use timezone-aware RFC3339 values and a narrow range containing the
ingested point. Confirm a foreign project UUID is not discoverable.

Do not validate tenant isolation with an unscoped ClickHouse query. Any direct diagnostic query must
include the expected project/organization identifiers.

## 5. M3.1 stop condition

M3.1 is complete only after automated/live query tests and the full release gate pass, the changes are
committed and pushed, and:

```text
## main...origin/main
```

is clean. Only then may M3.2 Metrics Explorer UI begin.
