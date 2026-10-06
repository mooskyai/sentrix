# Sentrix Coding Guideline

## 1. Purpose

This document defines the engineering rules for Sentrix. The goal is predictable code, explicit tenant boundaries, testable APIs, and an architecture that can grow from a modular monolith into independently scaled telemetry services without rewriting the control plane.

These rules apply to production code, migrations, tests, scripts, Docker configuration, and documentation.

## 2. Core principles

### 2.1 Correctness before abstraction

Prefer a small explicit implementation over an abstraction whose future use is speculative. Extract shared behavior after there are concrete repeated cases.

### 2.2 Tenant isolation is a backend invariant

Every organization-owned or project-owned read/write must derive authorization from the authenticated user and stored membership records.

Do not write code equivalent to:

```python
Project.objects.get(id=request.data["project_id"])
```

when the resource is tenant-owned.

Use a scoped queryset or service:

```python
Project.objects.filter(
    id=project_id,
    organization__memberships__user=request.user,
).get()
```

Frontend routing, hidden controls, or a supplied organization ID are never proof of authorization.

### 2.3 Keep the control plane and data plane separate

PostgreSQL is for relational control-plane state such as users, organizations, projects, permissions, dashboards, alert definitions, integrations, audit metadata, and billing configuration.

ClickHouse is for high-volume telemetry and analytical data.

Do not add raw metrics, log events, spans, or unbounded telemetry payloads to Django models without an architecture decision record explaining why.

### 2.4 Make failure visible

External dependencies must have bounded timeouts and errors must be observable. Do not silently catch exceptions unless the failure is intentionally degraded and is recorded through logs/metrics.

### 2.5 Tests are part of the feature

A behavior change without corresponding test coverage is incomplete. Regression fixes should include a test that fails before the fix and passes after it.

## 3. Python and Django

### 3.1 Runtime

- Python: `>=3.14,<3.15`
- Django: `>=6.1.1,<6.2`
- Package management: `uv`
- Formatting/linting: Ruff
- Static analysis: mypy
- Generated Django migration files are excluded from Ruff; migration correctness is enforced with Django migration checks and tests.
- Tests: pytest + pytest-django

Do not add a dependency when the standard library or an existing dependency is sufficient.

### 3.2 Style

- Maximum line length: 100 characters.
- Use type hints for public functions, services, selectors, and non-trivial helpers.
- Prefer `pathlib.Path` over manual path concatenation.
- Prefer timezone-aware datetimes.
- Prefer UUID primary keys for externally visible domain entities.
- Use enums/`TextChoices` for stable state machines.
- Do not use wildcard imports.
- Avoid module-level mutable state.
- Keep views thin; place reusable domain logic in services/selectors.

### 3.3 Django app boundaries

Each app owns one domain concept. A typical structure is:

```text
apps/<domain>/
├── admin.py
├── apps.py
├── models.py
├── permissions.py
├── selectors.py
├── serializers.py
├── services.py
├── urls.py
├── views.py
└── tests/
```

Not every app needs every file. Do not create empty architectural ceremony.

Recommended responsibilities:

- `models.py`: persistence and local invariants.
- `selectors.py`: reusable read/query logic.
- `services.py`: write workflows and cross-model business operations.
- `permissions.py`: DRF authorization primitives.
- `serializers.py`: request/response validation and representation.
- `views.py`: HTTP orchestration only.

### 3.4 Models and migrations

- Schema changes and migrations are committed together.
- Migrations must be deterministic and reviewable.
- Do not edit an applied migration in a shared environment; create a new migration.
- Every tenant-owned model has an explicit organization/project relationship or an unambiguous path to one.
- Add database constraints for invariants that must survive concurrent writes.
- Add indexes based on known query patterns, not guesses.

### 3.5 Transactions

Use `transaction.atomic()` for workflows that must commit together. Do not hold database transactions while calling remote services.

For concurrent state transitions, prefer database constraints, conditional updates, or `select_for_update()` where needed.

### 3.6 APIs

- API prefix: `/api/v1/`.
- Use nouns for resources.
- Return stable error shapes.
- Validate request payloads through serializers/forms, not ad-hoc dictionary access.
- Pagination is mandatory for collections that can grow without a hard upper bound.
- Do not expose internal exception messages to clients.
- Breaking API changes require a versioning decision.

A recommended error body is:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have access to this project."
  }
}
```

### 3.7 Authentication and authorization

V1 uses secure Django session authentication for the browser application.

Rules:

- CSRF protection remains enabled.
- Cookies are `HttpOnly`; secure cookies are mandatory in deployed HTTPS environments.
- Login endpoints are rate-limited before public deployment.
- Permission checks occur in API code even when the UI also hides actions.
- Role checks must use named role/permission helpers rather than string comparisons scattered through views.

### 3.8 Logging

Use Python logging with structured context when available.

Never log:

- passwords
- session cookies
- CSRF tokens
- API key secrets
- OAuth tokens
- raw authorization headers
- unrestricted telemetry payloads

Useful request context includes request ID, user ID, organization ID, project ID, operation, duration, and outcome.

## 4. React and TypeScript

### 4.1 Runtime and tooling

- React 19.3
- TypeScript 5.x
- Vite 8.3+
- React Router
- TanStack Query for server state
- Vitest 5 for unit/component tests
- ESLint for linting

### 4.2 TypeScript rules

- `strict` mode remains enabled.
- Avoid `any`. If unavoidable at a boundary, isolate and validate it.
- Prefer `unknown` for untrusted values.
- API response types live near the API client or feature using them.
- Do not duplicate backend enums manually without an explicit synchronization strategy.

### 4.3 Component rules

Prefer small components with clear ownership. Business behavior belongs in hooks/services, not giant page components.

Recommended feature structure:

```text
src/features/projects/
├── api.ts
├── components/
├── hooks.ts
├── pages/
├── types.ts
└── tests/
```

### 4.4 Server state

Use TanStack Query for data fetched from the API. Do not copy remote server state into global client stores without a concrete need.

Cache keys must include the tenant context where relevant, for example:

```ts
["projects", organizationId]
```

Changing organizations/projects must invalidate or isolate data so information from one tenant is not displayed under another tenant context.

### 4.5 Forms

Validate on both client and server. Client validation improves feedback; server validation is authoritative.

### 4.6 Accessibility

Interactive controls must be keyboard accessible, labelled, and usable without relying only on color. Charts added in later milestones must provide textual/summary alternatives where practical.

## 5. Security rules

The following are required before internet-facing deployment:

- HTTPS only.
- secure cookies.
- strict allowed-host/origin configuration.
- CSRF enabled for browser sessions.
- rate limiting on authentication and ingestion endpoints.
- request body limits.
- secret rotation procedure.
- dependency vulnerability scanning.
- least-privilege database users.
- no public ClickHouse/PostgreSQL/Redis ports in production.
- audit logging for privileged actions.

Secrets belong in environment/secret managers, never source control.

## 6. ClickHouse and telemetry rules

V1 only establishes connectivity. Later telemetry implementation must follow these rules:

- Every row includes tenant identifiers required for enforcement and query pruning.
- Ingestion validates tenant credentials before accepting data.
- Time-based partitioning and TTLs are storage-engine responsibilities.
- High-cardinality dimensions are reviewed deliberately.
- Queries always include bounded time ranges unless a privileged internal operation explicitly requires otherwise.
- Query limits and timeouts protect the cluster from unbounded scans.
- Raw telemetry schemas are versioned.

## 7. Redis rules

Redis is ephemeral infrastructure unless a feature explicitly documents persistence requirements.

Appropriate uses include caching, locks, throttling, short-lived coordination, and future queue/broker workloads.

Do not store the only copy of durable domain state in Redis.

## 8. Testing expectations

Backend changes should cover:

- happy path
- unauthorized request
- authenticated but wrong-tenant request
- role boundary when relevant
- validation failure
- important uniqueness/constraint behavior

Frontend changes should cover important behavior and user-visible states rather than implementation details.

See `V1_MILESTONE_TESTING.md` for the release gate.

## 9. Git and commit discipline

Keep commits scoped and reviewable. A commit should leave the repository in a buildable/testable state whenever possible.

Recommended conventional prefixes:

```text
feat:     user-visible capability
fix:      defect correction
docs:     documentation only
test:     test-only change
refactor: behavior-preserving code change
chore:    tooling/dependency/maintenance
ci:       continuous-integration change
```

Examples:

```text
feat(organizations): add tenant membership model
fix(projects): enforce membership in project detail queries
test(auth): cover CSRF-protected login flow
docs: document V1 control-plane boundary
```

Do not mix mass formatting with behavior changes.

## 10. Pull request checklist

A change is ready for review when:

- [ ] scope is clear and unrelated changes are excluded
- [ ] backend tenant checks are explicit
- [ ] migrations are included where required
- [ ] backend tests pass
- [ ] frontend tests pass where affected
- [ ] Ruff and mypy pass
- [ ] ESLint and TypeScript checks pass
- [ ] no secrets or generated credentials are committed
- [ ] docs are updated when behavior/setup/architecture changes
- [ ] new external dependencies have a concrete reason
- [ ] failure paths and observability have been considered

## 11. Definition of done

A feature is done only when its production behavior, authorization, tests, configuration, and documentation agree. Code that works only through a developer's local manual sequence is not complete.
