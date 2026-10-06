# Sentrix V1 M2 — Telemetry Ingestion Testing

## 1. Gate discipline

Each V1 M2 part has its own release gate. Do not start the next part until the current part is green,
committed, and pushed.

## 2. M2.1 — Project API Key Control Plane

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| KEY-001 | owner creates key | HTTP 201, one-time secret returned |
| KEY-002 | admin creates key | HTTP 201 |
| KEY-003 | editor creates key | HTTP 201 |
| KEY-004 | viewer lists keys | HTTP 403 |
| KEY-005 | viewer creates key | HTTP 403 |
| KEY-006 | viewer revokes key | HTTP 403 |
| KEY-007 | member targets foreign project UUID | HTTP 404/not accessible |
| KEY-008 | list after create | no `secret` or `secret_hash` |
| KEY-009 | persisted key | full token/plain secret not stored |
| KEY-010 | valid future expiry | accepted |
| KEY-011 | past expiry | validation error |
| KEY-012 | revoke | row retained and `revoked_at` populated |

### Backend gate

Run from the repository root:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose config --quiet
```

The existing backend suite has 12 tests before M2.1. M2.1 adds eight collected cases, so the expected
count is approximately 20 tests. Exact count is informational; zero failures and the security
assertions above are the release requirement.

### Manual verification

1. Sign in as an owner/admin/editor.
2. Create a key for an accessible project.
3. Copy the returned `secret` and confirm it appears only in that create response.
4. List keys and confirm only metadata is returned.
5. Revoke the key and confirm the row remains listed with `revoked_at`.
6. Sign in as a viewer and confirm list/create/revoke are denied.
7. Attempt an exact foreign project UUID and confirm it is inaccessible.

## 3. Stop condition

After M2.1 passes, commit and push it. Only then may M2.2 machine authentication be designed or
patched.


## 4. M2.2 — Machine Authentication Boundary

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| MACH-001 | valid Bearer key | authenticated project/organization/key context, HTTP 200 |
| MACH-002 | valid Bearer key | `last_used_at` populated |
| MACH-003 | wrong secret | HTTP 401, `last_used_at` unchanged |
| MACH-004 | revoked key | HTTP 401, `last_used_at` unchanged |
| MACH-005 | expired key | HTTP 401, `last_used_at` unchanged |
| MACH-006 | valid key without required scope | HTTP 403 |
| MACH-007 | malformed token | HTTP 401 |
| MACH-008 | unknown public prefix | HTTP 401 |
| MACH-009 | browser user without Bearer key | machine-only view returns HTTP 401 |
| MACH-010 | successful authentication | `request.auth` is the persisted project API key |

### Backend gate

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose config --quiet
```

M2.1 establishes a 20-test backend baseline. M2.2 adds nine collected machine-authentication cases,
so approximately 29 tests are expected. Exact count is informational; zero failures and all security
assertions are mandatory.

### Regression gate

M2.2 does not intentionally change frontend source or the Sentrix theme, but the release gate still
requires the existing frontend regression commands before commit:

```powershell
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test -- --run
docker compose exec web npm run build
```

There is no M2.2 migration. `makemigrations --check --dry-run` must report `No changes detected`.

## 5. M2.2 stop condition

After every M2.2 backend, frontend, documentation, and infrastructure gate passes, commit and push the
machine-authentication boundary. Only then may M2.3 OTLP/HTTP ingestion be designed or patched.

## 6. M2.3 — OTLP/HTTP Ingestion Gateway

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| OTLP-001 | valid metrics protobuf with test sink | HTTP 200, tenant-bound metrics batch |
| OTLP-002 | valid logs protobuf with test sink | HTTP 200, tenant-bound logs batch |
| OTLP-003 | valid traces protobuf with test sink | HTTP 200, tenant-bound traces batch |
| OTLP-004 | missing project key | HTTP 401 |
| OTLP-005 | key lacks `telemetry:write` | HTTP 403 |
| OTLP-006 | malformed protobuf | HTTP 400 with OTLP Status |
| OTLP-007 | unsupported JSON media type | HTTP 415 |
| OTLP-008 | body exceeds configured limit | HTTP 413 |
| OTLP-009 | valid gzip body | decoded and delivered to test sink |
| OTLP-010 | malformed gzip | HTTP 400 |
| OTLP-011 | unsupported content encoding | HTTP 415 |
| OTLP-012 | non-empty batch with default unavailable sink | HTTP 503, not falsely acknowledged |
| OTLP-013 | empty valid request | HTTP 200 empty Export*ServiceResponse |

### Dependency refresh

M2.3 adds official OpenTelemetry protobuf dependencies. Regenerate the lockfile and rebuild the API
container before testing:

```powershell
cd backend
uv lock
cd ..
docker compose build api
docker compose up -d api
```

### Release gate

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test -- --run
docker compose exec web npm run build
docker compose config --quiet
git diff --check
```

M2.3 introduces no schema migration. `makemigrations --check --dry-run` must report no changes.

## 7. M2.3 stop condition

Commit and push the protocol gateway only after the dependency lock, automated tests, static checks,
frontend regression gate, and Compose validation all pass. Only then may M2.4 ClickHouse telemetry
schema work begin.


## 8. M2.4 — ClickHouse Telemetry Schema

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| CH-001 | schema apply | three idempotent `CREATE TABLE IF NOT EXISTS` statements |
| CH-002 | expected telemetry tables | metrics, logs, spans definitions present |
| CH-003 | tenant invariant | every table contains organization/project IDs |
| CH-004 | metric representation | number/histogram/exponential-histogram/summary fields preserved |
| CH-005 | table partitioning | monthly partition expression is defined |
| CH-006 | physical tenant ordering | sorting keys start with organization/project |
| CH-007 | schema validation | exact live columns/types and keys are accepted |
| CH-008 | schema drift | missing/changed columns or keys are reported |

### Live ClickHouse verification

Apply the schema and then validate the live server:

```powershell
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema --check
```

Both commands must succeed. The second command must report all three tables as valid.

### Release gate

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test -- --run
docker compose exec web npm run build
docker compose config --quiet
git diff --check
```

M2.4 introduces ClickHouse schema only. Django's migration check must still report no changes.

## 9. M2.4 stop condition

Commit and push the ClickHouse schema only after live schema application/validation and all repository
quality gates pass. Only then may M2.5 wire OTLP normalization and durable writes.

## 10. M2.5 — End-to-End OTLP to ClickHouse

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-001 | metrics OTLP/HTTP request | HTTP 200 and tenant-scoped metric row |
| E2E-002 | logs OTLP/HTTP request | HTTP 200 and tenant-scoped log row |
| E2E-003 | traces OTLP/HTTP request | HTTP 200 and tenant-scoped span row |
| E2E-004 | two independent project credentials | rows remain isolated by project ID |
| E2E-005 | ClickHouse insert unavailable | HTTP 503 and no false acknowledgement |
| E2E-006 | real OTel Python SDK + OTLP/HTTP exporter | exported span reaches ClickHouse |

### Dependency refresh

M2.5 adds SDK/exporter dependencies for the real interoperability test:

```powershell
cd backend
uv lock
cd ..
docker compose build api
docker compose up -d api
```

### Live schema prerequisite

```powershell
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema --check
```

### Release gate

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema --check
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test -- --run
docker compose exec web npm run build
docker compose config --quiet
git diff --check
```

The integration tests require the Compose ClickHouse service. They use unique project UUIDs rather
than truncating shared tables, so repeated local runs remain safe.

## 11. M2.5 stop condition

Commit and push the durable OTLP-to-ClickHouse path only after all three signal integrations, tenant
isolation, real OpenTelemetry exporter interoperability, schema validation, and repository quality
gates pass. Only then may M2.6 API-key management UI work begin.

## 12. M2.6 — API Key Management UI

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| UIKEY-001 | project workspace navigation | Settings resolves to the current tenant/project route |
| UIKEY-002 | viewer opens Settings | read-only guidance, no API-key list request |
| UIKEY-003 | authorized key list | prefix/scope/status metadata rendered, no raw secret |
| UIKEY-004 | create key | name + optional expiry sent to current project endpoint |
| UIKEY-005 | create response | raw secret displayed in one-time transient state |
| UIKEY-006 | project context changes | one-time secret state is discarded |
| UIKEY-007 | revoke key | explicit confirmation, DELETE request, current project query refreshed |
| UIKEY-008 | customer-facing copy | no V1/M2/patch identifiers shown in the UI |

### Frontend release gate

```powershell
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test -- --run
docker compose exec web npm run build
```

The pre-M2.6 frontend baseline has six tests. M2.6 adds three credential-management component cases,
so approximately nine tests are expected. Exact count is informational; zero failures and the secret
handling/RBAC assertions are mandatory.

### Backend and infrastructure regression gate

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema --check
docker compose config --quiet
git diff --check
```

M2.6 introduces no backend schema change and no new package dependency. The existing backend regression
suite must remain green.

## 13. M2.6 stop condition

Commit and push the project API-key management UI only after role-aware behavior, one-time secret
handling, frontend quality gates, backend regressions, schema validation, and documentation all pass.
Only then may M2.7 operational verification and final M2 documentation work begin.
