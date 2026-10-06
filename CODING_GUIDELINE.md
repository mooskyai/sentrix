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

V1 M1 uses secure Django session authentication for the browser application.

Rules:

- CSRF protection remains enabled.
- Cookies are `HttpOnly`; secure cookies are mandatory in deployed HTTPS environments.
- Login endpoints are rate-limited before public deployment.
- Permission checks occur in API code even when the UI also hides actions.
- Role checks must use named role/permission helpers rather than string comparisons scattered through views.

V1 M2 machine credentials follow additional rules:

- API keys are project-scoped control-plane records and resolve to exactly one project/organization.
- Store only a public prefix and a one-way hash of the secret; never persist the full token.
- Return the full token only from the create response; list responses never expose `secret_hash`.
- Initial machine scope is `telemetry:write`; add scopes only for concrete capabilities.
- Revocation is metadata-preserving through `revoked_at`, not hard deletion.
- Optional expiry must be validated as a future timestamp.
- `last_used_at` is updated only after successful machine authentication; M2.1 does not fabricate use.
- Owner/admin/editor may manage project keys; viewers and foreign-tenant callers may not.

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

V1 M1 only establishes connectivity. V1 M2 telemetry implementation must follow these rules:

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

## 12. Tenant-aware frontend routing

Project workspace URLs use organization/project slugs for navigation, never authorization.

Required rules:

- resolve workspace slugs only against organization/project data returned by authenticated,
  tenant-scoped API calls;
- never call an unscoped backend endpoint because a slug appeared in the URL;
- keep immutable UUIDs as backend/data-plane identifiers even when browser URLs use slugs;
- when organization/project context changes, navigate to a new canonical route instead of retaining
  stale tenant state;
- TanStack Query cache keys must remain tenant-safe as query scope becomes more granular;
- unknown or inaccessible organization/project route combinations render an unavailable state and
  must not reveal whether a foreign tenant resource exists;
- owner/admin/editor UI may expose project-write actions while viewer UI is read-only, but every
  write still requires backend role enforcement.

Workspace section routes may be created before their telemetry implementation only when the UI makes
their unavailable/not-connected state explicit. Do not render sample telemetry in production paths
to make an unfinished data-plane feature appear complete.

## 12. Tailwind and Sentrix visual-system rules

The frontend uses Tailwind CSS 4 with the official Vite plugin. Keep theme configuration in `frontend/src/theme.css` using `@theme`; do not add a legacy
`tailwind.config.js` unless a concrete capability requires it.

Rules:

- reuse Sentrix theme tokens instead of introducing one-off hex values in React components;
- prefer Tailwind utilities in markup for new components and `@apply` for existing shared semantic
  classes when incremental migration keeps the component API clearer;
- keep operational screens dense: avoid oversized cards, excessive vertical whitespace, and large
  decorative headings that reduce information density;
- primary actions use the restrained signal-teal family; violet is secondary emphasis, not a competing primary;
- avoid pure-white body text, black-on-neon controls, and decorative glow that produces unnecessary eye strain;
- normal, muted, helper, placeholder, and disabled labels must remain readable on their actual surface; do not make important text disappear by stacking low-opacity text on dark backgrounds;
- warning/read-only, success, and error states use their semantic tokens and never rely on color alone;
- target WCAG AA contrast for normal interactive and informational text while keeping the palette visually soft;
- focus-visible states must remain obvious for keyboard users;
- responsive layouts must preserve tenant/project context and action discoverability;
- CSS visibility/disabled state is never authorization; backend permission checks remain mandatory.


## 13. Machine authentication implementation rules

V1 M2.2 introduces the reusable machine-authentication primitive. These rules are mandatory for every
endpoint that consumes a project API key:

- machine authentication must be explicitly enabled on the endpoint; do not add project API keys to
  global DRF authentication defaults;
- accept project credentials only through the Bearer authorization scheme and validate the Sentrix
  token shape before database lookup;
- verify the secret with Django's password-hashing API; never compare plaintext secrets directly;
- reject unknown, revoked, and expired credentials with a generic authentication failure;
- derive `organization_id`, `project_id`, `api_key_id`, and scopes from the persisted credential rather
  than caller-supplied tenant identifiers;
- update `last_used_at` only after the secret and credential state authenticate successfully;
- enforce endpoint capabilities with named scope permissions after authentication;
- a valid credential without a required scope is an authorization failure, not an authentication
  failure;
- keep browser session authentication and machine authentication separate trust paths;
- never log the bearer value, raw secret, stored hash, or unrestricted request payload.

The initial required telemetry capability remains `telemetry:write`. Additional scopes require a real
endpoint capability and corresponding tests; do not create speculative permission matrices.

## 14. OTLP/HTTP protocol-boundary rules

M2.3 introduces the first public telemetry protocol boundary. Required rules:

- keep OTLP routes at `/v1/metrics`, `/v1/logs`, and `/v1/traces`; do not nest them under the Sentrix
  control-plane `/api/v1/` namespace;
- authenticate before parsing telemetry bodies and derive tenant identity exclusively from the project key;
- accept only protocol encodings that are implemented faithfully; M2.3 accepts binary protobuf and
  does not approximate OTLP/JSON with generic protobuf JSON parsing;
- use official OpenTelemetry generated protobuf message classes instead of hand-written wire models;
- support `identity` and `gzip` request encodings and enforce the configured size limit after
  decompression;
- return non-retryable 4xx statuses for bad data, unsupported encodings, and oversized payloads as
  appropriate; use 503 when a valid batch cannot be durably accepted;
- never return OTLP success for non-empty telemetry that has only been decoded and then discarded;
- keep the decoder independent of ClickHouse schema/SQL so M2.4 can add storage without changing the
  external protocol contract;
- never log raw bearer credentials or unrestricted telemetry payloads.


## 15. ClickHouse telemetry-schema rules

M2.4 establishes the first durable telemetry schema. Required rules:

- manage telemetry tables through explicit ClickHouse schema code/commands, not Django models or
  PostgreSQL migrations;
- every telemetry table carries `schema_version`, `organization_id`, and `project_id`;
- physical sorting keys begin with tenant/project identity before signal-specific dimensions;
- time-partition raw telemetry by month unless measured behavior justifies a different partition;
- do not add TTLs, projections, codecs, or skip indexes speculatively;
- metric storage must preserve the distinction between number, histogram, exponential-histogram, and
  summary data instead of coercing all values into one scalar;
- trace and span identifiers use fixed-width lowercase-hex storage contracts suitable for correlation;
- keep ClickHouse DDL independent from the OTLP HTTP decoder;
- M2.4 may create/validate tables but must not acknowledge non-empty OTLP requests until M2.5 wires a
  durable write path;
- schema validation must compare live columns/types and partition/sort keys before M2.4 is accepted.
