# Sentrix V1 Milestone — Platform Foundation

## 1. Goal

V1 establishes a secure multi-tenant control-plane foundation on which metrics, logs, traces, dashboards, and alerting can be built.

The milestone is intentionally not an observability feature demo. Its purpose is to remove the highest-cost architectural risks early: tenancy, authentication, authorization, persistence boundaries, local infrastructure, API conventions, and engineering quality gates.

## 2. User outcome

At the end of V1, a user can:

```text
Open application
      |
      v
Sign in
      |
      v
Create organization
      |
      v
Create project
      |
      v
Open project workspace
```

A user who is not a member of that organization cannot discover or access the project through the API.

## 3. Scope

### 3.1 Repository foundation

Deliver:

- Python 3.14 backend project managed with uv
- Django 6.1.x (`>=6.1.1,<6.2`)
- React 19.3 + TypeScript + Vite 8.3+
- Docker Compose development environment
- PostgreSQL
- Redis
- ClickHouse
- `.env.example`
- backend/frontend formatting, linting, typing, and test commands
- Windows-friendly verification script
- architecture and development documentation

### 3.2 Authentication

Deliver first-party browser session authentication:

- CSRF bootstrap endpoint
- login endpoint
- logout endpoint
- current-user endpoint
- protected API defaults

V1 does not implement social login, SAML, OIDC, MFA, password reset UI, or public self-registration workflows.

### 3.3 Organizations

Organization entity:

```text
id: UUID
name
slug
created_at
updated_at
```

Membership entity:

```text
id: UUID
organization_id
user_id
role
created_at
updated_at
```

Initial roles:

```text
OWNER
ADMIN
EDITOR
VIEWER
```

Creating an organization automatically makes its creator an owner.

### 3.4 Projects

Project entity:

```text
id: UUID
organization_id
name
slug
created_by
created_at
updated_at
```

Requirements:

- slug is unique inside an organization
- list/detail APIs are scoped to memberships
- owner/admin/editor can create projects
- viewer can read but cannot create/update/delete projects
- project creation accepts an organization only when the caller belongs to it

### 3.5 Health and dependency checks

Deliver:

```text
GET /api/v1/health/live/
GET /api/v1/health/ready/
```

Readiness checks PostgreSQL, Redis, and ClickHouse and exposes per-component status without leaking secrets.

### 3.6 React shell

Deliver:

- router
- login page
- authenticated application shell
- overview page
- organization creation form
- project creation form
- organization/project navigation foundation
- API client with session credentials and CSRF handling
- loading, empty, and basic error states

The V1 UI does not need polished observability charts yet.

## 4. Explicitly out of scope

Do not expand V1 with:

- raw telemetry ingestion
- OpenTelemetry collector configuration
- Kafka/Redpanda
- metrics/log/trace tables
- metrics explorer
- log search
- trace waterfall
- dashboard editor
- alerts
- incidents
- Kubernetes monitoring
- billing
- OAuth/SSO
- AI analysis

These are subsequent milestones and depend on the V1 tenant boundary.

## 5. Backend deliverables

### Authentication API

```text
GET  /api/v1/auth/csrf/
POST /api/v1/auth/login/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/
```

### Organization API

```text
GET    /api/v1/organizations/
POST   /api/v1/organizations/
GET    /api/v1/organizations/{organization_id}/
PATCH  /api/v1/organizations/{organization_id}/
DELETE /api/v1/organizations/{organization_id}/   optional until owner policy is finalized
```

### Project API

```text
GET    /api/v1/projects/
POST   /api/v1/projects/
GET    /api/v1/projects/{project_id}/
PATCH  /api/v1/projects/{project_id}/
DELETE /api/v1/projects/{project_id}/
```

Deletion may be disabled in the UI until soft-delete/retention rules are defined, but API authorization behavior must not be ambiguous.

## 6. Data invariants

The following must be enforced:

1. Organization slugs are globally unique in V1.
2. A user has at most one membership per organization.
3. Project slug is unique per organization.
4. Every project belongs to exactly one organization.
5. Every project creator is recorded where available.
6. A caller cannot list or retrieve another tenant's projects.
7. Viewer membership cannot mutate project state.
8. Organization creation produces owner membership atomically.

## 7. Security requirements

Before V1 is accepted:

- CSRF remains enabled.
- CORS origins are explicit.
- allowed hosts are configuration-driven.
- production settings do not default to debug mode.
- secrets are environment-driven.
- password authentication uses Django's built-in password hashing.
- tenant object queries are membership-scoped.
- backend enforces roles independently of the frontend.
- health endpoints do not return credentials or exception tracebacks.

## 8. Development experience

A new developer should be able to clone the repository and reach a running stack from documented commands without reverse-engineering local assumptions.

Required paths:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

and, for host-run application development:

```powershell
docker compose up -d postgres redis clickhouse
cd backend
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py runserver
```

```powershell
cd frontend
npm install
npm run dev
```

## 9. Quality gate

V1 cannot be marked complete unless:

```text
Backend
  ruff check
  ruff format --check
  mypy
  pytest

Frontend
  eslint
  tsc --noEmit
  vitest
  vite build

Infrastructure
  docker compose config
  service health checks
  Django migrate --check
```

The detailed test matrix is in `V1_MILESTONE_TESTING.md`.

## 10. Acceptance criteria

### Repository

- [ ] Python version constraint requires 3.14.
- [ ] Django starts successfully.
- [ ] React dev server starts successfully.
- [ ] Docker Compose configuration validates.
- [ ] `.env.example` documents all required settings.

### Infrastructure

- [ ] PostgreSQL health check passes.
- [ ] Redis health check passes.
- [ ] ClickHouse health check passes.
- [ ] Django readiness reports dependency failures with HTTP 503.

### Authentication

- [ ] Valid user can log in.
- [ ] Invalid credentials are rejected without leaking which field was wrong.
- [ ] `me` rejects anonymous requests.
- [ ] Logout invalidates the authenticated session.
- [ ] state-changing browser calls require CSRF protection.

### Tenancy

- [ ] Organization creation adds owner membership atomically.
- [ ] User sees only organizations where membership exists.
- [ ] User sees only projects under member organizations.
- [ ] Guessing a project UUID from another organization returns no accessible object.
- [ ] Project creation rejects organizations outside the caller's memberships.

### RBAC

- [ ] Owner can create/update project.
- [ ] Admin can create/update project.
- [ ] Editor can create/update project.
- [ ] Viewer can read project.
- [ ] Viewer cannot create/update/delete project.

### Frontend

- [ ] Anonymous user is directed to login.
- [ ] Authenticated user can load the application shell.
- [ ] User can create an organization.
- [ ] User can create a project.
- [ ] API failures have a visible state.
- [ ] project/org state does not leak across tenant switches.

### Documentation

- [ ] README commands match the repository.
- [ ] architecture boundaries are documented.
- [ ] coding rules are documented.
- [ ] testing evidence can be reproduced from documented commands.

## 11. Exit decision

When all mandatory acceptance checks pass, commit V1 as a stable baseline before starting telemetry ingestion.

The next milestone should introduce **machine/API-key authentication and OpenTelemetry ingestion**, not dashboard polish. The product needs trustworthy data flow before advanced visualization.
