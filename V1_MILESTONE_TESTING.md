# Sentrix V1 Milestone Testing

## 1. Purpose

This document defines the verification required before V1 can be accepted. It is a release gate, not a list of optional test ideas.

Testing is split into static checks, unit/API tests, tenant-isolation tests, frontend tests, infrastructure tests, and a final end-to-end smoke test.

## 2. Test environments

### Required developer environment

- Windows 11 or a supported Unix environment
- Python 3.14
- Docker Compose v2
- Node.js 24+
- PostgreSQL container
- Redis container
- ClickHouse container

### CI expectation

CI should use isolated service containers and a fresh database. Tests must not depend on a developer's persistent Docker volumes.

## 3. Backend static gate

Run:

```powershell
cd backend
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Pass criteria:

- no Ruff violations in maintained source code (generated Django migration files are excluded)
- formatting clean
- mypy exits zero
- Django system check exits zero
- no model changes are missing migrations

## 4. Backend automated tests

The development API image includes the `dev` dependency group. Run tests either from the host environment or directly in Docker Compose.

Host:

```powershell
cd backend
uv run pytest -q
```

Docker Compose:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest -q
```

### Authentication cases

| ID | Scenario | Expected |
| --- | --- | --- |
| AUTH-001 | valid username/password | HTTP 200, session created |
| AUTH-002 | invalid password | HTTP 400/401-equivalent safe response |
| AUTH-003 | anonymous `me` | HTTP 403/401 |
| AUTH-004 | authenticated `me` | current user payload |
| AUTH-005 | logout | session no longer authenticates |
| AUTH-006 | state-changing request without CSRF in browser flow | rejected by CSRF middleware |

### Organization cases

| ID | Scenario | Expected |
| --- | --- | --- |
| ORG-001 | create organization | organization created |
| ORG-002 | creator membership | exactly one OWNER membership |
| ORG-003 | list organizations | only member organizations |
| ORG-004 | retrieve foreign organization | not found/denied |
| ORG-005 | duplicate slug | validation error |
| ORG-006 | duplicate membership | database/serializer prevents duplicate |

### Project cases

| ID | Scenario | Expected |
| --- | --- | --- |
| PRJ-001 | owner creates project | created |
| PRJ-002 | admin creates project | created |
| PRJ-003 | editor creates project | created |
| PRJ-004 | viewer creates project | denied |
| PRJ-005 | member lists projects | only projects for member organizations |
| PRJ-006 | foreign UUID detail request | not found/denied |
| PRJ-007 | create project in foreign org | denied |
| PRJ-008 | duplicate slug in same org | validation error |
| PRJ-009 | same slug in different org | allowed |
| PRJ-010 | viewer updates project | denied |

## 5. Tenant isolation tests

Tenant isolation is the most important V1 test category.

Fixture:

```text
User A -> Org A -> Project A
User B -> Org B -> Project B
```

Required assertions:

1. User A's organization list does not contain Org B.
2. User A's project list does not contain Project B.
3. User A cannot retrieve Project B using its exact UUID.
4. User A cannot update/delete Project B using its exact UUID.
5. User A cannot create a project by submitting Org B's exact UUID.
6. User B has the symmetric restrictions.

A response code alone is not enough. Tests should also assert that the underlying foreign resource was not mutated.

## 6. Database tests

Verify constraints directly where meaningful:

- organization slug unique
- membership `(organization, user)` unique
- project `(organization, slug)` unique
- cascade/protect behavior matches the model decision
- UUID primary keys are generated server-side

Run migration verification against PostgreSQL, not only SQLite.

```powershell
docker compose up -d postgres
cd backend
uv run python manage.py migrate --noinput
uv run python manage.py migrate --check
```

## 7. Health tests

### Liveness

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live/
```

Expected:

```json
{"status":"ok"}
```

### Readiness healthy

With PostgreSQL, Redis, and ClickHouse running:

```powershell
Invoke-WebRequest http://localhost:8000/api/v1/health/ready/
```

Expected: HTTP 200 and all configured components report `ok`.

### Readiness degraded

Stop one dependency, for example Redis:

```powershell
docker compose stop redis
```

Call readiness again.

Expected:

- HTTP 503
- Redis reports failure
- no password, connection string, traceback, or sensitive environment value is exposed

Restart the service after the test:

```powershell
docker compose start redis
```

## 8. Frontend gate

Run:

```powershell
cd frontend
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

Pass criteria:

- ESLint exits zero
- TypeScript exits zero
- Vitest exits zero
- production build succeeds

### Required UI behavior

| ID | Scenario | Expected |
| --- | --- | --- |
| UI-001 | anonymous load | login view shown |
| UI-002 | successful login | app shell shown |
| UI-003 | current user fetch pending | stable loading state |
| UI-004 | current user request fails | recoverable error/login state |
| UI-005 | create organization succeeds | organization appears/selects |
| UI-006 | create project succeeds | project appears/selects |
| UI-007 | API mutation fails | visible error, no false success state |

## 9. Docker Compose gate

Validate configuration:

```powershell
docker compose config --quiet
```

Start cleanly:

```powershell
docker compose down -v
docker compose up --build -d
```

Inspect:

```powershell
docker compose ps
```

Expected:

- `postgres` healthy
- `redis` healthy
- `clickhouse` healthy
- `api` running
- `web` running

Check logs for repeated crashes:

```powershell
docker compose logs --tail 200 api web postgres redis clickhouse
```

## 10. End-to-end smoke test

Perform against a fresh environment.

### Step A — create users

Create two users (`user-a`, `user-b`) using Django admin or shell.

### Step B — user A

- sign in
- create Org A
- create Project A
- record Org A and Project A UUIDs

### Step C — user B

- sign in
- create Org B
- create Project B
- record Org B and Project B UUIDs

### Step D — cross-tenant checks

While authenticated as User A, directly request User B's organization/project URLs and attempt a write using Org B's UUID.

Expected: every cross-tenant operation is inaccessible and no resource changes.

### Step E — dependency check

Stop ClickHouse and confirm readiness becomes `503`, then restore it and confirm readiness returns `200`.

## 11. Security review checklist

Before V1 sign-off:

- [ ] `.env` is ignored by Git
- [ ] no credentials in repository history for the milestone branch
- [ ] `DEBUG` is not hardcoded true
- [ ] allowed hosts are configurable
- [ ] CORS does not use wildcard with credentials
- [ ] CSRF is not disabled
- [ ] session cookie configuration is documented for HTTPS production
- [ ] tenant scoping is tested on list and detail endpoints
- [ ] viewer write restrictions are tested
- [ ] health errors do not expose stack traces/secrets
- [ ] dependencies are reviewed for known critical vulnerabilities

## 12. Performance sanity checks

V1 does not need load-test certification, but obvious regressions should be caught.

Minimum checks:

- organization list query count does not grow linearly with displayed membership details
- project list uses membership filtering in the database rather than Python post-filtering
- readiness calls use short dependency timeouts

## 13. Test evidence template

Record this in the milestone PR/release note:

```text
Commit:
Date:
Environment:
Python:
Node:
Docker:

Backend
[ ] ruff check
[ ] ruff format --check
[ ] mypy
[ ] django check
[ ] makemigrations --check
[ ] pytest

Frontend
[ ] lint
[ ] typecheck
[ ] test
[ ] build

Infrastructure
[ ] docker compose config
[ ] clean compose startup
[ ] liveness
[ ] readiness healthy
[ ] readiness dependency failure

Security / tenancy
[ ] cross-tenant list isolation
[ ] cross-tenant detail isolation
[ ] cross-tenant mutation isolation
[ ] viewer mutation denied
```

## 14. Release gate

V1 is accepted only when all mandatory checks pass on the intended baseline commit. A known failing test is a blocker unless the acceptance criteria are formally changed in `V1_MILESTONE.md` with the reason documented.
