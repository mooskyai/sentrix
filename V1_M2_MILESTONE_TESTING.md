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
