# Sentrix

## M6 browser acceptance evidence producer — candidate

`backend/scripts/m6_acceptance_smoke.py` is an opt-in **independent Python
process** sending actual three-service OTLP/HTTP protobuf metrics, logs and
trace spans with exact parentage and `host.name`/`k8s.*` resource labels.
See [operator runbook](docs/M6_ACCEPTANCE_PRODUCER.md). It reads a temporary
project write key from stdin and prints nonsecret run/trace identifiers.
A successful HTTP response is not proof of ClickHouse read-back, real
Kubernetes inventory or M6 browser acceptance. M6.2–M6.4 operator records
remain open until independently observed and committed; M6.5 is not started.

## Automatic workspace selection and stale preference recovery — 2026-10-24 candidate

When the API lists an authorized organization and project, the header selects the
first usable organization/project pair automatically. A valid manual choice persists
in user-scoped, versioned `localStorage`, not as an authorization token. On a
removed or mismatched saved choice, the header falls back to server-listed IDs
and persists `stale: true` until a fresh explicit selection. Existing valid deep
links override preferences; invalid routes still fail closed. No telemetry query
window, backend access policy or acceptance status is changed.

## M6.4 observed service relationships — implementation candidate

The Services page gains an opt-in **Observed relationships** map from exact same-trace
parent/child spans. A bounded, session-authorized API provides directional evidence
and sample trace links; it never assumes missing edges mean downtime. No graph
store or schema change. See `V1_M6_MILESTONE.md` and `M6_4_BROWSER_ACCEPTANCE.md`.
The M6.2 and M6.3 operator acceptance gates remain open; this candidate is not
verified, accepted, or committed merely by applying the patch.

## GitHub Actions integration-test dependencies — 2026-10-24

The backend CI job runs on the GitHub-hosted Ubuntu runner, **not** inside the
Docker Compose `api` container. Its services must explicitly start PostgreSQL,
Redis, and ClickHouse; CI connects to their published host ports at `localhost`.
`pytest -q` includes real OTLP/ClickHouse persistence and tenant isolation tests.
See `Testing&QA.md` for CI verification and `Debugging.md` for connection errors.
A successful local `scripts/verify.ps1` run does not prove hosted CI services exist.

## Current product direction and release status — 2026-10-24

Sentrix is being developed toward **production-grade observability workflows**,
using vendor-neutral OpenTelemetry collection. This is a *roadmap*, not a claim
of feature parity. See **[ROADMAP.md](ROADMAP.md)** for staged deliverables,
security/quality gates and an implemented-vs-planned capability ledger.

At reviewed `main` (`0939cca`), M6.1 is accepted; M6.2 Services detail and M6.3
Infrastructure discovery plus framework documentation are implemented, committed
and pushed. The last reported full gate passed **182 backend / 58 frontend**
tests, but M6.2/M6.3 manual browser and real-producer acceptance remains open.
M6.4 service relationships and M6.5 closeout have **not** been implemented.
Do not treat old 'candidate' snippets below as current release status.

## Historical 2026-10-23 onboarding patch note (superseded by current status)

Authenticated users see **Documentation** in the left sidebar; the guide offers Laravel, Node.js,
React and Next.js with copyable install/configure/run snippets. The API reference is kept at its
existing direct route but hidden from navigation; project Settings retains only the setup link.
The React guide sends no project secret to the browser. See `docs/FRAMEWORK_QUICKSTART.md` and
`docs/PROJECT_TELEMETRY_SETUP.md`. This change requires frontend and full release verification
plus browser acceptance; it does not close the outstanding M6.2/M6.3 manual gates.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 infrastructure discovery is being implemented from stored OTLP `resource_attributes` only.
The project Infrastructure workspace and read API show co-observed host/Kubernetes attribute sets,
counts and observed times. This candidate is **not yet operator accepted or pushed**. M6.2 manual
browser acceptance remains open. See `M6_3_BROWSER_ACCEPTANCE.md`. No Kubernetes API, inventory or
health claims.

## Compact workspace navigation and inspection — pushed; final acceptance pending

The shared top header now holds the organization and project selectors for the browser session.
Project-scoped sidebar links appear only after both selections resolve to authorized workspace
resources; changing organization clears project context instead of auto-selecting one. Service,
log-record and trace-span inspection use accessible right-side drawers on desktop (full width on
small screens). Page and control spacing is reduced without changing any telemetry query/tenant
boundary. The visually approved single-level card hierarchy (one content card for
Services, Metrics, Logs, Traces and Settings; sibling cards for Overview, Dashboards
and Alerts) is committed and pushed at `a4bcb4c`. The final post-correction
Windows/Docker release gate passed on 2026-10-22 (170 backend, 50 frontend
tests and all required checks). M6.2 manual browser acceptance remains open.
See `DESIGN.md`, `Testing&QA.md` and `M6_2_BROWSER_ACCEPTANCE.md`.
M6.3 has not started.

## Opt-in demo dataset for V1 M1–M6.2

To populate an isolated synthetic example for the Services, Metrics, Logs, Traces,
Dashboards, Alerts and API Keys screens, run from the repository root:

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py seed_demo --username YOUR_LOGIN
```

`YOUR_LOGIN` must be an existing active Sentrix user. The command creates two demo
organizations and project-scoped OTLP telemetry, never prints credentials, and does not
send webhooks. See [DEMO_SEEDING.md](DEMO_SEEDING.md) for full coverage, safe rerun behavior,
and limitations. **Synthetic records are not real-data operational acceptance.**

## M6.2 service-detail workspace (implemented/pushed; browser acceptance pending)

The Services workspace reads the observed service catalog and the separate
`/api/v1/projects/{project_id}/services/detail/` endpoint for exact service and environment,
including an empty environment, within a bounded UTC window. Detail lists actual bounded
metric names, recent error logs (severity 17+) and observed trace IDs. Trace references
carry project and time-window context; generic Metrics and Logs links do not prefilter.
No inferred health, ownership, SLO or resource inventory is presented.
The source was committed/pushed at `a0e7881`, and the demo seeder at `4b34f3c`.
The complete release gate passed (170 backend / 44 frontend tests) on Windows/Docker.
**Manual browser acceptance is still unreported.** Use `M6_2_BROWSER_ACCEPTANCE.md`
with `DEMO_SEEDING.md` before declaring M6.2 accepted or starting M6.3.

## V1 M6.1 service catalog (verified, pushed)

The first M6 read boundary is `GET /api/v1/projects/{project_id}/services/catalog/`, a
session-authenticated, membership-scoped summary of observed `(service_name, environment)` pairs across
ClickHouse metrics, logs, and spans. Queries default to the last 24 hours (maximum seven days) and cap
results at 500 identities with explicit `truncated` status. This is **not** a service health registry or
Kubernetes inventory. M6.1 passed the release gate and was committed as `2c1b5a2`.

## V1 M6.2 Services workspace

The project Services section lists exact observed `(service_name, environment)` identities in
the selected 1h, 6h, 24h or 7d window. Inspect shows observed signal counts, first/last UTC
timestamps and separately fetched, capped metric/error-log/trace references. It distinguishes
empty, error and truncated results. It is not an inventory, service health or SLO view.
Project-specific explorer links preserve context; Metrics/Logs remain unfiltered until the
operator applies supported controls. Browser acceptance has not yet been reported.

## Project documentation

Sentrix keeps a **V1-to-current documentation set** synchronized with each development slice. Start with [`PRD.md`](PRD.md) for product scope, [`DESIGN.md`](DESIGN.md) for UI patterns, [`ARCHITECTURE.md`](ARCHITECTURE.md) for system boundaries, [`DATABASE.md`](DATABASE.md) for persistence, [`API.md`](API.md) for contracts, and [`AGENTS.md`](AGENTS.md) for mandatory contributor/documentation rules. See [`ProjectImplementation.md`](ProjectImplementation.md) for status, [`Setup.md`](Setup.md) for onboarding, [`FeatureDevelopment.md`](FeatureDevelopment.md) for implementation workflow, [`Authentication&Security.md`](Authentication&Security.md) for security, [`Integrations.md`](Integrations.md) for external protocols, [`Testing&QA.md`](Testing&QA.md) for test gates, and [`Debugging.md`](Debugging.md) for diagnosis. `README.md` is the canonical Readme; do not create a case-only duplicate on Windows. Existing `V1_M*_MILESTONE*.md` files remain the detailed slice/acceptance record.

**Sentrix** is a multi-tenant observability and monitoring platform for metrics, logs, traces, dashboards, alerts, and infrastructure visibility. This starter establishes the production-minded foundation using **Python 3.14, Django 6.1.x, React 19.3, PostgreSQL, Redis, and ClickHouse**.

The repository intentionally starts with the **control plane**. It establishes authentication, organizations, projects, tenant scoping, RBAC boundaries, health checks, local infrastructure, testing conventions, and a React application shell before metrics, logs, and traces are introduced.

![Sentrix logo](assets/sentrix-logo.png)

**Recommended repository name:** `sentrix`

## Product identity

- Product: **Sentrix**
- Category: observability and monitoring platform
- Primary brand asset: `assets/sentrix-logo.png`
- Frontend-served asset: `frontend/public/brand/sentrix-logo.png`
- Public API prefix: `/api/v1/`
- Docker Compose project: `sentrix`

The brand name must remain separate from domain boundaries. Metrics, logs, traces, organizations, projects, and alerts should use domain terminology in code instead of brand-prefixed model names.

## Why this architecture

Sentrix has two very different workloads:

- **Control plane:** users, organizations, projects, permissions, dashboards, alert definitions, integrations, audit records, billing metadata.
- **Telemetry data plane:** metrics, logs, traces, events, ingestion, aggregation, retention, and high-volume analytical queries.

Django and PostgreSQL own the control plane. ClickHouse owns telemetry storage. Redis is used for caching, coordination, rate-limit state, and future background processing. Telemetry must not be modeled as ordinary Django/PostgreSQL rows.

```text
React + TypeScript
       |
       | HTTPS / JSON
       v
Django control plane -------------------- PostgreSQL
       |                                     users
       |                                     organizations
       |                                     projects
       |                                     memberships
       |
       +---------------------------------- Redis
       |                                     cache / coordination
       |
       +---- query boundary ------------ ClickHouse
                                             metrics / logs / traces

Future telemetry path:
SDKs / Agents -> OpenTelemetry Collector -> Ingestion Gateway -> Stream -> Workers -> ClickHouse
```

## Repository layout

```text
.
├── backend/                  Django control plane
│   ├── apps/
│   │   ├── accounts/         Session authentication API
│   │   ├── common/           Health/readiness and shared primitives
│   │   ├── organizations/    Organizations, membership and RBAC
│   │   └── projects/         Tenant-scoped projects
│   └── config/               Django settings and routing
├── frontend/                 React + TypeScript application
│   └── public/brand/         Sentrix product assets
├── scripts/                  Developer convenience scripts
├── assets/                   Repository-level Sentrix brand assets
├── ARCHITECTURE.md
├── CODING_GUIDELINE.md
├── V1_MILESTONE.md
├── V1_MILESTONE_TESTING.md
├── V1_M2_MILESTONE.md
├── V1_M2_MILESTONE_TESTING.md
├── docker-compose.yml
└── .env.example
```

## Prerequisites

Recommended host tooling:

- Python **3.14**
- [uv](https://docs.astral.sh/uv/)
- Node.js **24 LTS or newer**
- npm **11 or newer**
- Docker Desktop with Docker Compose v2
- Git

On Windows 11, PowerShell 7 is recommended.

## Fastest start: Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

After services become healthy:

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000/api/v1/`
- Liveness: `http://localhost:8000/api/v1/health/live/`
- Readiness: `http://localhost:8000/api/v1/health/ready/`
- ClickHouse HTTP: `http://localhost:8123`

Create a Django superuser:

```powershell
docker compose exec api /opt/venv/bin/python manage.py createsuperuser
```

## Local development without containerizing the app processes

Keep PostgreSQL, Redis, and ClickHouse in Docker:

```powershell
docker compose up -d postgres redis clickhouse
```

Backend:

```powershell
cd backend
uv sync --group dev
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
```

Frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend dev server proxies `/api` to Django by default.

## First API flow

1. Open the frontend and create or use a Django user.
2. Sign in through the React login form.
3. Create an organization.
4. Create a project inside that organization.
5. Verify that another user without membership cannot list or access that project.

Example API surface included by this starter:

```text
GET    /api/v1/health/live/
GET    /api/v1/health/ready/
GET    /api/v1/auth/csrf/
POST   /api/v1/auth/login/
POST   /api/v1/auth/logout/
GET    /api/v1/auth/me/
GET    /api/v1/organizations/
POST   /api/v1/organizations/
GET    /api/v1/organizations/{id}/
PATCH  /api/v1/organizations/{id}/
GET    /api/v1/projects/
POST   /api/v1/projects/
GET    /api/v1/projects/{id}/
PATCH  /api/v1/projects/{id}/
GET    /api/v1/projects/{id}/api-keys/
POST   /api/v1/projects/{id}/api-keys/
DELETE /api/v1/projects/{id}/api-keys/{api_key_id}/
```

## Dependency locking

The Sentrix starter does not invent lockfiles without resolving the package indexes. On the first development setup, run `uv sync --group dev` in `backend` and `npm install` in `frontend`, then commit the generated `backend/uv.lock` and `frontend/package-lock.json`. From that point onward, CI and release builds should use the committed locks.

## Quality commands

The development API image installs the `dev` dependency group so tests, Ruff, and mypy are available inside the container. Production images should use a separate build target that excludes development tooling.

Backend from the host:

```powershell
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Backend from Docker Compose:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/mypy .

Generated Django migrations are excluded from Ruff; use `makemigrations --check --dry-run` plus the backend test suite to verify migration consistency.
```

Frontend:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Repository smoke checks:

```powershell
./scripts/verify.ps1
```

## Environment configuration

Copy `.env.example` to `.env` and change secrets before any shared or deployed environment.

Important settings:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django cryptographic signing key |
| `DJANGO_DEBUG` | Development-only debug mode |
| `DJANGO_ALLOWED_HOSTS` | Allowed Host header values |
| `POSTGRES_*` | Control-plane database |
| `REDIS_URL` | Cache/coordination connection |
| `CLICKHOUSE_*` | Telemetry database connection |
| `CORS_ALLOWED_ORIGINS` | Explicit browser origins allowed to call the API |
| `CSRF_TRUSTED_ORIGINS` | Origins trusted for state-changing session requests |

Never commit `.env`.

## Engineering rules

The complete rules are in [CODING_GUIDELINE.md](CODING_GUIDELINE.md). The non-negotiable items are:

1. Every tenant-owned query is scoped from the authenticated user's memberships. Never trust `organization_id` from the browser by itself.
2. PostgreSQL stores control-plane state, not raw telemetry.
3. API behavior is covered by tests before a milestone is accepted.
4. Schema changes include migrations in the same commit.
5. Security checks live on the backend. Hiding a button in React is not authorization.
6. No feature is complete until README/docs and tests are updated.

## Milestone documents

- [V1_MILESTONE.md](V1_MILESTONE.md) defines the completed V1 M1 platform-foundation scope.
- [V1_MILESTONE_TESTING.md](V1_MILESTONE_TESTING.md) defines the V1 M1 test matrix and release gate.
- [V1_M2_MILESTONE.md](V1_M2_MILESTONE.md) defines the telemetry-ingestion milestone and its ordered parts.
- [V1_M2_MILESTONE_TESTING.md](V1_M2_MILESTONE_TESTING.md) defines the M2 per-part acceptance gates.
- [V1_M3_MILESTONE.md](V1_M3_MILESTONE.md) defines the metrics-query/dashboard milestone and ordered delivery.
- [V1_M3_MILESTONE_TESTING.md](V1_M3_MILESTONE_TESTING.md) defines the M3 acceptance and operational closeout gates.
- [V1_M4_MILESTONE.md](V1_M4_MILESTONE.md) defines logs, trace lookup, correlation, and M4 closeout.
- [V1_M4_MILESTONE_TESTING.md](V1_M4_MILESTONE_TESTING.md) defines the M4 test and operational verification matrix.
- [V1_M5_MILESTONE.md](V1_M5_MILESTONE.md) defines project alert rules, evaluation, notifications, and ordered delivery.
- [V1_M5_MILESTONE_TESTING.md](V1_M5_MILESTONE_TESTING.md) defines M5 alerting acceptance and closeout gates.
- [ARCHITECTURE.md](ARCHITECTURE.md) defines system boundaries from the control plane through telemetry ingestion.

## V1 M1 definition of done

V1 M1 is complete when a user can authenticate, create an organization, create a project, and access only resources permitted by their membership and role; the React application can operate against those APIs; PostgreSQL, Redis, and ClickHouse health are observable; and all documented backend/frontend quality gates pass.

V1 M2 starts the real telemetry path. Part M2.1 adds project-scoped API keys only; machine authentication, OTLP ingestion, and ClickHouse telemetry persistence remain blocked until M2.1 is green, committed, and pushed.

### V1 M2.1 project API keys

Project API keys are control-plane credentials for future telemetry ingestion. Owner/admin/editor roles may create, list, and revoke keys for member projects; viewers cannot manage them. Raw secrets are returned exactly once at creation, only a one-way hash is persisted, and revocation preserves metadata by setting `revoked_at`.

## Project workspace flow

The control-plane UI now has a canonical tenant-aware project workspace route:

```text
/orgs/:organizationSlug/projects/:projectSlug
/orgs/:organizationSlug/projects/:projectSlug/:section
```

Supported workspace sections are `overview`, `metrics`, `logs`, `traces`, `dashboards`, `alerts`, and
`settings`. Overview and settings contain real control-plane state. Metrics, Logs, Traces, and
Dashboards and Alerts now use project-scoped application/query boundaries backed by real persisted
data or control-plane configuration. Alerts reads persisted current evaluation state and never triggers
evaluation from the browser.

Workspace behavior:

- organization and project switchers navigate only through resources returned by the authenticated,
  tenant-scoped APIs;
- owner/admin/editor memberships get project-write UI while viewer memberships are shown as
  read-only;
- typing a foreign or unknown slug does not grant access and resolves to an unavailable workspace;
- backend UUID detail/update/delete endpoints remain the authorization boundary and continue to use
  membership-scoped querysets;
- project cards on the overview page open the canonical project workspace route.

Frontend routing is a navigation concern only. URL organization/project slugs must never be treated
as authorization evidence.

## Sentrix visual system

The web application uses **Tailwind CSS 4** through the official Vite plugin. Sentrix keeps the
framework configuration CSS-first: `frontend/src/styles.css` imports Tailwind and the dedicated `frontend/src/theme.css` token file;
`theme.css` defines product design tokens with `@theme`, while the global stylesheet composes the
current semantic component classes with Tailwind utilities.

The default product theme is **Sentrix Spectrum**, a compact observability-focused dark interface:

- deep navy canvas and elevated blue-black surfaces with softened off-white text instead of pure white;
- restrained signal teal for primary actions and active navigation, avoiding neon treatment;
- electric violet as a secondary data/feature accent;
- dedicated amber, green, and red states for read-only/warning, success, and errors;
- readable muted, helper, placeholder, and disabled text without low-opacity labels disappearing into the canvas;
- comfortable contrast that preserves legibility while avoiding glare from pure-white text or over-saturated controls;
- tighter 52px application chrome, compact controls, reduced panel padding, and denser lists;
- consistent radii, borders, focus rings, buttons, inputs, selects, badges, and empty states.

After pulling a change that modifies frontend packages, refresh the existing Compose node_modules
volume before running frontend gates:

```powershell
docker compose exec web npm install
docker compose restart web
```

The visual system must not encode authorization. Disabled/hidden project controls improve UX, while
Django remains the security boundary.


## V1 M2.2 machine authentication boundary

M2.2 turns the project credentials from M2.1 into a reusable machine-authentication boundary without
changing browser authentication or accepting telemetry yet. Machine-only endpoints opt in to
`ProjectApiKeyAuthentication`; the global DRF default remains Django session authentication for the
first-party web application.

Machine requests use:

```text
Authorization: Bearer sentrix_pk_<public-prefix>_<secret>
```

Successful authentication verifies the stored one-way secret hash, rejects revoked or expired keys,
derives organization/project identity from the credential, exposes the authenticated key as
`request.auth`, and updates `last_used_at`. `HasProjectApiKeyScopes` enforces endpoint-required scopes;
the initial machine scope remains `telemetry:write`.

Request payloads and URLs must never override the tenant identity established by the credential. M2.2
adds no OTLP routes, telemetry parsing, or ClickHouse writes; those remain blocked behind M2.3 and
later parts.

## V1 M2.3 OTLP/HTTP ingestion gateway

M2.3 exposes the standard OTLP/HTTP signal paths outside the Sentrix control-plane `/api/v1/`
namespace:

```text
POST /v1/metrics
POST /v1/logs
POST /v1/traces
```

Each endpoint requires `Authorization: Bearer <project-api-key>` with `telemetry:write`. The tenant and
project are derived only from that credential. This part uses the official OpenTelemetry generated
protobuf messages and initially accepts `application/x-protobuf`; gzip and identity content encodings
are supported. The request body is bounded by `OTLP_MAX_REQUEST_BYTES` (64 MiB by default).

OTLP/JSON is deliberately not accepted in M2.3. OTLP JSON has protocol-specific identifier encoding
rules that differ from generic protobuf JSON, so Sentrix will not claim JSON compatibility until a
fully compliant decoder is covered by tests.

M2.3 also refuses to acknowledge non-empty telemetry while no durable sink exists: the default sink
returns HTTP 503 so standard exporters can retry rather than silently losing data. Tests replace that
sink seam to prove metrics, logs, and traces decode correctly and carry the credential-derived tenant
context. M2.4 defines ClickHouse schemas; M2.5 wires durable persistence and then enables successful
acknowledgement for non-empty telemetry.

After applying M2.3, refresh backend dependencies and the lockfile before running gates:

```powershell
cd backend
uv lock
cd ..
docker compose build api
docker compose up -d api
```


## V1 M2.4 ClickHouse telemetry schema

M2.4 establishes the durable ClickHouse table contract without wiring OTLP requests into writes yet.
The schema is managed explicitly through Django:

```powershell
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema
docker compose exec api /opt/venv/bin/python manage.py clickhouse_schema --check
```

The command creates and validates three `MergeTree` tables:

```text
sentrix_metrics
sentrix_logs
sentrix_spans
```

Every table carries `schema_version`, `organization_id`, `project_id`, signal time, service/environment,
instrumentation-scope context, resource attributes, and signal-specific fields. Tables partition by
month and order by tenant/project plus useful signal dimensions and time. No retention TTL is guessed
in M2.4; retention remains an explicit product/storage decision.

Metrics use one row per data point and preserve dedicated fields for gauge/sum, histogram,
exponential-histogram, and summary representations instead of flattening every metric into a single
number. Logs preserve trace/span correlation IDs. Spans preserve trace identity plus event/link JSON
payloads for later normalization decisions.

M2.4 does not change the M2.3 sink behavior: non-empty OTLP requests still return HTTP 503. M2.5 is
responsible for translating decoded OTLP batches into these schemas and acknowledging only after a
durable ClickHouse write succeeds.

## V1 M2.5 end-to-end OTLP persistence

M2.5 connects the authenticated OTLP gateway to the ClickHouse tables introduced in M2.4. Decoded
OpenTelemetry requests are normalized into tenant-bound rows and inserted synchronously before an OTLP
success response is returned.

The persistence path is:

```text
OTLP/HTTP
  -> project API-key authentication
  -> official protobuf decode
  -> signal-specific row normalization
  -> ClickHouse insert
  -> OTLP success response
```

Metric normalization emits one ClickHouse row per OpenTelemetry data point and preserves number,
histogram, exponential-histogram, and summary shapes. Resource and instrumentation-scope attributes are
copied into their schema maps, while `service.name` and deployment environment attributes populate the
indexed service/environment columns. Logs preserve severity/body and trace correlation. Spans preserve
trace lineage, status, timing, events, and links.

ClickHouse failures remain retryable: the sink converts persistence failures into HTTP 503 instead of
acknowledging telemetry that was not durably written. M2.5 tests also send a real span through the
OpenTelemetry Python SDK plus OTLP/HTTP exporter and verify that it reaches the authenticated Sentrix
endpoint and becomes a tenant-scoped ClickHouse row.

M2.5 adds OpenTelemetry SDK/exporter packages to the backend development dependency group. Refresh the
lockfile and rebuild the API image before running the release gate:

```powershell
cd backend
uv lock
cd ..
docker compose build api
docker compose up -d api
```

## V1 M2.6 project API-key management UI

Project workspace settings expose the existing project credential control plane at:

```text
/orgs/:organizationSlug/projects/:projectSlug/settings
```

Owners, admins, and editors can list safe API-key metadata, create a telemetry credential with an
optional expiry, copy the raw secret from the one-time creation result, and revoke existing keys.
Viewers see a read-only access message and the browser does not issue API-key management requests for
that project.

The raw credential is deliberately kept out of TanStack Query server-state caches, browser storage,
URLs, and logs. It lives only in transient component state after creation and is cleared when the
message is dismissed or when project context changes. Subsequent list responses show only the public
prefix, scopes, expiry, last-used time, revocation state, and other safe metadata.

The settings UI uses the same project UUID already resolved through the authenticated tenant-scoped
workspace. Browser role checks improve UX only; Django remains authoritative for list/create/revoke
authorization.

## V1 M2.7 operational verification

M2.7 closes the telemetry-ingestion milestone by making the existing path reproducible from bootstrap
through durable ClickHouse storage. It does not add telemetry query/explorer behavior.

For a fresh local environment, use the repository bootstrap instead of manually re-creating its steps:

```powershell
.\bootstrap.cmd
```

On bash-compatible systems:

```bash
./bootstrap.sh
```

The bootstrap preserves existing volumes, creates `.env` from `.env.example` only when needed, starts
the Compose stack, applies PostgreSQL migrations, applies and validates the ClickHouse schema, checks
Django, verifies liveness/readiness, and creates the first Django superuser only when none exists. It
never runs `docker compose down -v`; that command deletes local PostgreSQL and ClickHouse data.

After signing in, create an organization and project, then open:

```text
/orgs/<organization>/projects/<project>/settings
```

Create a telemetry credential and copy the full `sentrix_pk_...` value immediately. The full secret is
shown only once and cannot be recovered from later list responses.

To prove that a real OpenTelemetry HTTP exporter can authenticate with that credential and persist a
tenant-scoped span, run:

```powershell
./scripts/verify-m2.ps1
```

The script prompts for the API key using a secure PowerShell prompt, checks that all Compose services
are running, verifies the web/API health endpoints and ClickHouse schema, sends a real OTLP/HTTP span
through `/v1/traces`, and confirms the resulting `sentrix_spans` row using the project ID derived from
the authenticated key. The credential is piped over stdin and is never printed by the verification
tooling.

OpenTelemetry OTLP/HTTP exporters may also use the standard base endpoint configuration:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer sentrix_pk_...
```

With a base OTLP/HTTP endpoint, standard exporters send traces, metrics, and logs to `/v1/traces`,
`/v1/metrics`, and `/v1/logs` respectively. Sentrix currently supports binary protobuf only; OTLP/JSON
is intentionally unsupported. Do not commit exporter credentials to `.env`, scripts, or source files.

Operational failure meanings:

| Status | Meaning |
| --- | --- |
| `400` | malformed OTLP protobuf/gzip payload |
| `401` | missing, malformed, unknown, revoked, or expired project credential |
| `403` | authenticated credential lacks `telemetry:write` |
| `413` | request exceeds `OTLP_MAX_REQUEST_BYTES` |
| `415` | unsupported media type or content encoding |
| `503` | durable ClickHouse acceptance is unavailable; exporter should retry |

Run the complete release gate before committing M2.7:

```powershell
./scripts/verify.ps1
```

That script runs the backend tests/static checks, Django migration/schema checks, frontend lint/typecheck/
tests/build, Compose validation, and `git diff --check` against the running development stack.

## V1 M3.1 metrics query foundation

M3 begins the read path over the telemetry stored by M2. M3.1 adds session-authenticated, project-scoped
metrics query endpoints for the first-party web application; it does not add the explorer UI yet.

```text
GET /api/v1/projects/{project_id}/metrics/catalog/
GET /api/v1/projects/{project_id}/metrics/series/
```

Both endpoints resolve the requested project through the authenticated user's membership-scoped Django
queryset before ClickHouse is touched. A foreign project UUID therefore returns `404`, and organization/
project predicates sent to ClickHouse are derived from that authorized project rather than query-string
input.

Queries use a half-open `[start, end)` RFC3339 time window. When omitted, the window defaults to the
last hour; a single request may cover at most seven days. Catalog results are capped at 500 metrics and
numeric series at 5,000 points. The series endpoint accepts exact `service_name` and `environment`
filters and currently returns only rows with `number_value` (OpenTelemetry gauge/sum number points).
Histograms, exponential histograms, and summaries stay visible in catalog metadata but are not flattened
into fake scalar series.

Example:

```text
GET /api/v1/projects/<project-uuid>/metrics/catalog/?start=2026-10-09T04:00:00Z&end=2026-10-09T05:00:00Z
GET /api/v1/projects/<project-uuid>/metrics/series/?metric_name=process.cpu.utilization&start=2026-10-09T04:00:00Z&end=2026-10-09T05:00:00Z
```

ClickHouse query failures return HTTP `503` without exposing dependency internals. M3.2 will connect the
existing project Metrics workspace to this boundary after M3.1 is green, committed, and pushed.

## V1 M3.2 metrics explorer UI

The project Metrics workspace now reads the M3.1 catalog and numeric-series endpoints directly:

```text
/orgs/<organization>/projects/<project>/metrics
```

The explorer defaults to the previous hour and supports 1 hour, 6 hour, 24 hour, and 7 day windows.
Users can select recently observed scalar metrics, apply exact `service.name` and deployment-environment
filters, refresh the current window, inspect an observed-point plot, and review the latest returned
points in a table.

The explorer remains semantically conservative. Catalog entries backed only by histogram,
exponential-histogram, or summary points are visible but cannot be selected as scalar series. Gauge and
sum values are displayed exactly as returned by the query API; the browser does not derive rates,
deltas, averages, percentiles, or histogram statistics. When the server marks a series as truncated,
the UI warns that the visible result is incomplete rather than implying full coverage.

Loading, empty, query-error, and dependency-unavailable states are distinct. Switching project context
remounts the explorer and its query keys include the immutable project UUID, time window, selected
metric, and applied filters so telemetry from one project cannot be reused as another project's browser
state.

## V1 M3.3 first dashboard panels

The project Dashboards workspace now renders a small read-only dashboard whose configuration is stored
in PostgreSQL while every telemetry value continues to come from the M3.1 ClickHouse metrics query API.
M3.3 intentionally supports one dashboard surface per project and at most six panels; multiple named
dashboards, layout editing, and arbitrary query builders remain later work.

Project members can read panel configuration at:

```text
GET /api/v1/projects/{project_id}/dashboard-panels/
```

Owner/admin/editor memberships can pin or remove panel configuration:

```text
POST   /api/v1/projects/{project_id}/dashboard-panels/
DELETE /api/v1/projects/{project_id}/dashboard-panels/{panel_id}/
```

The browser does not ask users to re-enter metric names manually. In the Metrics explorer, an authorized
writer can select a scalar metric, choose the existing bounded time range, apply exact service/environment
filters, and use **Pin current query to dashboard**. The saved control-plane record contains only the
panel title, metric name, bounded range, exact filters, order, and creation metadata. It contains no raw
telemetry values.

The Dashboards route then reuses `/metrics/series/` for each configured panel with a dashboard-specific
500-point cap. Panels show latest/min/max/raw-point count plus the same observed-point plot used by the
explorer. Those statistics are simple summaries of the returned raw numeric points; Sentrix still does
not derive rates, deltas, histogram statistics, or percentiles.

After pulling M3.3 into an already-running local stack, apply the new control-plane migration before
using the dashboard API:

```powershell
docker compose exec api /opt/venv/bin/python manage.py migrate
```

Fresh bootstrap/startup continues to apply Django migrations automatically.

## V1 M3.4 operational verification and closeout

M3 closes with one production-shaped verification command:

```powershell
./scripts/verify-m3.ps1
```

The script recreates the current Compose services with `--build --force-recreate` while preserving
PostgreSQL and ClickHouse persistent volumes. Use `-SkipComposeRecreate` only while debugging an already
fresh stack; it is not the final M3 acceptance path. The script then checks frontend/API readiness and
the ClickHouse schema, securely prompts for a project telemetry key, exports a uniquely named real
OTLP/HTTP metric, and proves that metric is durably present under the project/organization derived from
the credential.

M3.4 also verifies the first-party read path rather than stopping at a direct ClickHouse diagnostic. It
prompts for a normal Sentrix browser username/password, establishes a real CSRF/session-authenticated
HTTP session, resolves the telemetry-key project through that user's memberships, and verifies the fresh
metric through both `/metrics/catalog/` and `/metrics/series/` with exact service/environment filters.
The browser user must have owner/admin/editor access because the smoke temporarily creates one dashboard
panel; a project with six panels must free one slot before running the closeout.

The script prints exact Metrics and Dashboards URLs and pauses for a human browser confirmation that the
fresh value is visible in both views. The temporary panel is removed after confirmation (and cleanup is
attempted on failure), then the normal `scripts/verify.ps1` release gate runs. A successful M3 closeout
ends with:

```text
M3 operational verification passed.
```

Secrets are read from secure prompts and are never printed. `SENTRIX_OTLP_API_KEY` and
`SENTRIX_BROWSER_USERNAME` may be supplied for convenience, but the browser password is always prompted
securely. The operational metric remains in ClickHouse as real telemetry; only the temporary dashboard
configuration is deleted. Generated TypeScript `.tsbuildinfo` state is ignored and no longer versioned,
so the production frontend build does not dirty the repository.

## V1 M4.1 logs query foundation

M4 extends the first-party telemetry read path to the durable log rows already written by M2. The first
slice adds one session-authenticated, project-scoped endpoint:

```text
GET /api/v1/projects/{project_id}/logs/search/
```

As with metrics, Django resolves the project through the authenticated user's membership-scoped queryset
before ClickHouse is opened. ClickHouse receives the organization/project IDs from that authorized
project, never from log attributes or caller-supplied tenant fields.

The search defaults to the previous hour, allows at most seven days, returns at most 1,000 rows, and
orders results newest-first. Optional filters are exact `service_name`/`environment`, OpenTelemetry
`min_severity_number` (`0..24`), a bounded case-insensitive `body_contains` substring, and an exact
32-hex non-zero `trace_id`. All dynamic values are typed ClickHouse parameters; M4.1 does not expose
arbitrary SQL, regex, or attribute-expression syntax.

Returned rows preserve raw log metadata including severity, body, event name, resource/scope/log
attributes, flags, and trace/span IDs. The all-zero storage sentinel for an absent correlation ID is
returned as `null`. Trace lookup and browser navigation are deliberately deferred to M4.3; a trace ID
in a log response is searchable data, not tenant authority.

The Logs workspace remains a truthful placeholder until M4.2 connects it to this API.


## V1 M4.2 logs explorer UI

The project Logs workspace now reads the M4.1 project-scoped endpoint directly:

```text
/orgs/<organization>/projects/<project>/logs
```

The explorer defaults to the previous hour and offers the same bounded 1h/6h/24h/7d windows used by
other telemetry views. Operators may select a bounded result limit (100/200/500/1000), refresh the
window, and apply the M4.1 filters for exact service/environment, minimum OpenTelemetry severity,
case-insensitive body substring, and exact trace ID. Filter inputs do not issue a request on every
keystroke; the query changes only when the operator applies or clears filters.

Rows remain newest-first and render the raw log body, severity, service/environment, trace/span IDs,
instrumentation scope, resource attributes, log attributes, flags, and dropped-attribute count. Missing
correlation IDs stay visibly absent. A non-zero trace ID is displayed as data only in M4.2; it does not
become a link until M4.3 adds an independently project-authorized span/trace query boundary.

Loading, healthy-empty, query-error, and truncated states are distinct. The browser never connects to
ClickHouse directly, and every TanStack Query key includes the immutable project UUID, explicit time
window, row limit, and applied filters so one project's log result cannot be reused as another's state.

## V1 M4.3 trace lookup and log correlation

Sentrix now exposes a session-authenticated, project-scoped exact trace lookup:

```text
GET /api/v1/projects/{project_id}/traces/{trace_id}/?start=<rfc3339>&end=<rfc3339>
```

The trace ID must be a non-zero 32-character hexadecimal OpenTelemetry ID. Lookups default to the last
hour, are capped at seven days, and return at most 1,000 spans (`500` by default). Django resolves the
project through the caller's memberships before ClickHouse is opened, and the ClickHouse query always
uses the authorized organization/project IDs plus typed trace/time parameters.

The project Traces workspace supports manual exact-ID lookup with 1h/6h/24h/7d bounded windows. It shows
raw span start/end timing, duration, service/environment, span and parent IDs, span kind/status, scope/
resource/span attributes, trace state, stored event/link JSON, flags, and dropped counts. Missing parent
spans are not created; when a returned span references a parent outside the bounded response, the UI says
that the parent was not returned.

Correlated log rows with a valid trace ID now expose **Open trace**. That link carries the Logs query's
same start/end window to `/traces`, but the destination still performs its own session-authenticated
project lookup and span query. Knowing a trace ID therefore never grants cross-project access.

## V1 M4.4 operational verification and closeout

M4 closes with one production-shaped correlated telemetry verification command:

```powershell
./scripts/verify-m4.ps1
```

The command rebuilds and force-recreates the current Compose services while preserving persistent
volumes, verifies web/API readiness and the ClickHouse schema, securely reads a project telemetry key,
and sends a uniquely marked root/child trace plus an ERROR log correlated to the child through the
public `/v1/traces` and `/v1/logs` endpoints.

The helper derives organization/project identity by authenticating that project key and proves both
signals are durably present with scoped ClickHouse queries. The verification then authenticates a normal
Django browser session, independently resolves the same project through membership, and proves the fresh
telemetry through `/logs/search/` and `/traces/{trace_id}/` before asking for a real Logs -> **Open
trace** browser confirmation.

The browser user only needs project read membership; M4.4 creates no temporary dashboard/configuration
records. Unique smoke telemetry remains in ClickHouse as ordinary data. After browser confirmation the
script runs the complete `scripts/verify.ps1` release gate. `-SkipComposeRecreate` and
`-SkipReleaseGate` exist only for debugging and are not valid for final M4 acceptance.

Secrets are never printed: `SENTRIX_OTLP_API_KEY` may supply the project key and
`SENTRIX_BROWSER_USERNAME` may supply the username, while the browser password is always prompted
securely. The telemetry key is otherwise read via a secure prompt and piped to the helper over stdin.
Generated `frontend/tsconfig.app.tsbuildinfo` is ignored/untracked so frontend typecheck/build execution
no longer dirties the repository.

A successful final run ends with:

```text
M4 operational verification passed.
```

After committing/pushing the closeout, `git status -sb` must show `## main...origin/main` before M4 is
considered complete.

## V1 M5.1 project alert-rule foundation

M5 begins with alert configuration only. The new project-scoped API is:

```text
GET   /api/v1/projects/{project_id}/alert-rules/
POST  /api/v1/projects/{project_id}/alert-rules/
GET   /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
PATCH /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
DELETE /api/v1/projects/{project_id}/alert-rules/{alert_rule_id}/
```

Any project member may read rules. Owner/admin/editor memberships may create, edit, enable/disable, and
delete them; viewers remain read-only. Foreign project UUIDs and rule IDs are resolved through the same
membership-scoped project boundary used elsewhere.

The first rule shape is intentionally narrow and metric-only. It stores a metric name, 1h/6h/24h/7d
bounded window, optional exact service/environment filters, a comparator (`gt`, `gte`, `lt`, or `lte`),
a finite numeric threshold, and enabled state. Rule names are unique per project and the V1 control plane
allows at most 50 rules per project.

M5.1 does not evaluate rules, query ClickHouse during rule creation, show firing state, create incidents,
or send notifications. The project Alerts route remains an explicit not-connected state until the M5.3
browser slice. M5.2 will establish the evaluator/state boundary first.

## V1 M5.2 metric evaluation and current alert state

M5.2 adds a current PostgreSQL state record for every alert rule while keeping metric samples in
ClickHouse. Rule list/detail responses expose one of `pending`, `ok`, `firing`, `no_data`, `error`, or
`disabled`, plus evaluation/transition timestamps, the source metric timestamp when one uniquely exists,
and a bounded error code. This is current operational state only; Sentrix does not persist metric values
or an evaluation-history stream in PostgreSQL.

Evaluation remains outside HTTP request handlers. Run the one-shot evaluator with:

```powershell
docker compose exec api /opt/venv/bin/python manage.py evaluate_alerts
```

An optional `--project-id <project-uuid>` scopes a run. The evaluator derives organization/project
identity from each persisted rule relationship, uses the configured half-open 1h/6h/24h/7d window and
exact service/environment filters, and reads only scalar `number_value` points. No point is `no_data`;
ClickHouse failure, a non-finite value, or more than one point sharing the newest timestamp is `error`.
A unique newest point is compared directly with `gt`, `gte`, `lt`, or `lte` without rate/delta/average
or histogram semantics.

Evaluation snapshots the rule version before opening ClickHouse and refuses to persist a stale result if
the rule changes while the query is in flight or a newer evaluation already committed. Evaluation-
affecting edits reset enabled rules to `pending`; disabling makes the state `disabled`. M5.2 does not add
notification delivery, incidents,
history, scheduler infrastructure, or the Alerts browser UI; M5.3 owns the workspace.

## V1 M5.3 Alerts workspace

The project Alerts route now uses the existing project-scoped alert-rule API. Any project member can
read rule configuration and persisted current state; owner/admin/editor memberships can create, edit,
enable/disable, and delete rules. Viewer sessions remain read-only in the UI and Django remains the
authorization boundary.

The browser exposes the same narrow M5 rule grammar: metric name, 1h/6h/24h/7d window, exact optional
service/environment filters, `gt`/`gte`/`lt`/`lte`, finite threshold, and enabled state. Rule cards show
`pending`, `ok`, `firing`, `no_data`, `error`, or `disabled` plus persisted evaluation timestamps,
source-point timestamp, and bounded error code. The UI does not invent an observed metric value because
M5.2 deliberately leaves raw telemetry in ClickHouse.

`Refresh state` only re-reads the project rule API. Creating, editing, toggling, deleting, refreshing, or
opening the Alerts route never runs the evaluator from an HTTP request and never accesses ClickHouse
directly from the browser. Evaluation cadence remains an external worker/scheduler concern for later M5
work.

## V1 M5.4 notification channels and dispatch

M5.4 adds project-scoped webhook notification channels and a durable delivery queue in PostgreSQL. Any
project member may read channel metadata and recent delivery state. Owner/admin/editor memberships may
create, update, enable/disable, and delete channels through:

```text
GET    /api/v1/projects/{project_id}/notification-channels/
POST   /api/v1/projects/{project_id}/notification-channels/
GET    /api/v1/projects/{project_id}/notification-channels/{channel_id}/
PATCH  /api/v1/projects/{project_id}/notification-channels/{channel_id}/
DELETE /api/v1/projects/{project_id}/notification-channels/{channel_id}/
GET    /api/v1/projects/{project_id}/notification-deliveries/?limit=100
```

Webhook endpoints are treated as sensitive configuration. Read responses expose only a redacted
`endpoint_display`; the full URL is never returned after write. Creation returns a derived HMAC signing
secret once. The API never returns that secret again, and outbound requests use `X-Sentrix-Timestamp`
and `X-Sentrix-Signature: sha256=<hex>` over `<timestamp>.<canonical-json-body>`. Losing the signing
secret requires recreating the channel. Production deployments must set a strong `DJANGO_SECRET_KEY`.

Outbound webhook egress is deny-by-default when `DJANGO_DEBUG=false`: configure exact permitted
hostnames with `NOTIFICATION_WEBHOOK_ALLOWED_HOSTS`. HTTP is disabled outside debug unless
`NOTIFICATION_WEBHOOK_ALLOW_HTTP=true` is set deliberately. Redirects are not followed. Endpoint
userinfo/fragments are rejected, response bodies and exception text are never persisted, and only bounded
error codes/status codes are stored.

Alert evaluation still performs no network delivery. A persisted state transition queues one delivery
per enabled project channel only for `non-firing -> firing` and direct `firing -> ok` recovery. Repeated
same-state evaluations, `firing -> no_data`, `firing -> error`, rule edits, and disable operations do not
invent recovery notifications. Delivery payloads snapshot rule configuration and state timestamps but do
not copy the observed metric value into PostgreSQL.

Dispatch runs outside HTTP requests with:

```powershell
docker compose exec api /opt/venv/bin/python manage.py dispatch_notifications
```

Use `--project-id <project-uuid>` to scope an operational run and `--limit <1..1000>` to bound work.
Delivery claims use a short PostgreSQL lease so overlapping workers do not normally double-send; expired
claims are recoverable. Each delivery receives at most three attempts with bounded backoff. Network/
timeout failures, HTTP 408/425/429, and 5xx responses are retryable; redirects and other 3xx/4xx results
are terminal. Disabled channels cancel still-pending deliveries. M5.4 intentionally adds no permanent
scheduler, Celery/Dramatiq dependency, incidents, email/Slack-specific adapters, or ClickHouse schema
change.

## V1 M5.5 operational verification and closeout

M5 closes with one production-shaped alerting verification command:

```powershell
./scripts/verify-m5.ps1
```

The verifier rebuilds and force-recreates the current Compose stack without deleting persistent volumes,
checks web/API readiness and ClickHouse schema, authenticates a normal browser session, and creates one
disposable project inside a writable organization. It creates a temporary project telemetry credential
through the normal control-plane API; the raw `sentrix_pk_...` secret stays only in process memory and is
piped to the OTLP helper over stdin.

The helper sends a uniquely named scalar metric through the public `/v1/metrics` endpoint and proves the
credential-derived organization/project row in ClickHouse. The temporary project then receives one alert
rule and one loopback webhook channel. A real firing value drives `pending -> firing`, the one-shot
evaluator queues one delivery, and the one-shot dispatcher sends a signed webhook to a disposable
receiver running inside the API container. A repeated firing evaluation must create no second delivery.
A second real OTLP point below the threshold then drives direct `firing -> ok` recovery and produces one
signed recovery webhook.

The operational script also creates a disposable project in an organization the browser user does not
belong to and confirms alert-rule/channel routes return `404`, verifies channel reads do not expose the
full endpoint or signing secret, checks the exact HMAC/delivery/event headers received by the loopback
receiver, and confirms both delivery rows finish `delivered` after one HTTP 204 attempt. Before cleanup it
prints the real Alerts workspace URL and requires a human confirmation that the temporary rule is visible
with final state `ok`.

Temporary PostgreSQL control-plane records and receiver files are removed even on failure. The uniquely
named raw metric rows remain ordinary ClickHouse telemetry, matching the earlier operational milestones.
After browser confirmation and cleanup the script runs the complete `scripts/verify.ps1` release gate.
`-SkipComposeRecreate` and `-SkipReleaseGate` are debugging conveniences only and are not valid for final
M5 acceptance.

`SENTRIX_BROWSER_USERNAME` may supply the session username. `SENTRIX_M5_ORGANIZATION_SLUG` may select a
writable organization when the user belongs to more than one; otherwise the script prompts. The browser
password is always read with a secure prompt. A successful final run ends with:

```text
M5 operational verification passed.
```

After committing and pushing the closeout, `git status -sb` must show `## main...origin/main` before V1
M5 is considered complete.

## Next: V1 M6 service catalog and infrastructure observability

With V1 M5 alerting complete, the next milestone turns existing OTLP metrics, logs, and spans into
project-scoped service and infrastructure views. M6 remains telemetry-derived: it does not introduce a
manual service inventory or copy discovered services/resources into PostgreSQL.

The ordered plan is:

1. M6.1 — tenant-safe service catalog query foundation across metrics, logs, and spans;
2. M6.2 — Services list/detail workspace with bounded multi-signal correlation;
3. M6.3 — host and Kubernetes resource discovery from preserved OpenTelemetry resource attributes;
4. M6.4 — bounded observed service map from real cross-service span parent/child relationships;
5. M6.5 — real OTLP operational verification, tenant-isolation proof, browser acceptance, and closeout.

The initial service identity is the exact `(service_name, environment)` pair already promoted by the
telemetry schemas. Discovery is time bounded (24-hour default, seven-day maximum) and descriptive: a
service or resource missing from the selected window is "not observed", not automatically down, deleted,
or unhealthy. M6 does not invent SLOs, ownership, Kubernetes inventory, or dependencies without telemetry
evidence.

Infrastructure discovery reads supported semantic-convention keys such as `host.name`,
`k8s.cluster.name`, `k8s.namespace.name`, workload names, `k8s.pod.name`, and `k8s.container.name` from
existing resource attributes. It does not contact the Kubernetes API or require cluster credentials.

The service map is likewise evidence based. V1 M6.4 may create an edge only when a stored child span can
be joined to its real parent span inside the same authorized project/trace and the service identities
differ. The UI will label those edges as observed span relationships rather than guaranteed network or
Kubernetes topology.

The detailed contract and acceptance matrix live in `V1_M6_MILESTONE.md` and
`V1_M6_MILESTONE_TESTING.md`. M6.1 was accepted at `2c1b5a2`; M6.2 code was
pushed at `a0e7881` and its demo fixture at `4b34f3c`. Browser acceptance remains open.

### Flat project workspace presentation (pre-M6.3 UI refinement)

Project pages render directly on the shared content surface instead of nesting
all explorer content inside another bordered panel. Distinct fact cards, charts,
tables and alerts remain where useful; Service inspection is also flat inside
its right-side drawer. See `UI_DENSITY_AND_DRAWERS.md` for browser acceptance.

The pre-M6.3 data-first layout refinement further removes borders from control bars
and table wrappers, with whitespace/rules instead of nested cards. It keeps one
page title and the shared header selectors; see `UI_DENSITY_AND_DRAWERS.md`.

The pre-M6.3 UI design uses single-level cards: a single surface for data-heavy
explorers, or separate sibling cards for Overview, Dashboards and Alerts.
Controls, tables and summaries never add another card inside that surface.
See `UI_DENSITY_AND_DRAWERS.md`.

## In-app documentation links — project setup and API reference

Project **Settings** now has two plain links, **Telemetry setup guide** (`/docs/telemetry-setup`) and **API reference** (`/docs/api-reference`). They open read-only guidance inside the current app without adding a project navigation tab. The setup guide covers project API-key creation, the one-time secret, protobuf OTLP/HTTP trace export from Python, endpoint and auth configuration, and troubleshooting. The API reference distinguishes session/CSRF-protected management and query APIs from bearer-key telemetry ingestion. Repository mirrors: [`docs/PROJECT_TELEMETRY_SETUP.md`](docs/PROJECT_TELEMETRY_SETUP.md) and [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

These links add no telemetry capability, do not authorize a project, and never transmit a raw key to a documentation route. Existing M6.2 and M6.3 operator acceptance gates remain unchanged.

## Service detail → telemetry explorer context (pending browser acceptance)

Inspecting an observed service now provides project-scoped deep links to Metrics,
Logs and Traces with the exact service/environment and observation range. Metrics
and Logs automatically apply these filters on arrival; Traces opens a real
observed trace reference when available, retaining the complete distributed
trace. Empty environments remain distinct from missing dimension filters.
See `docs/SERVICE_EXPLORER_NAVIGATION.md` for semantics and regression checks.
This UI correction requires browser verification and the full release gate;
it does not close the existing M6 acceptance checklists.
