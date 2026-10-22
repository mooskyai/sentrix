# Sentrix — Product Requirements Document

## Pre-M6.3 UI refinement — committed; final acceptance pending

The shared right-side header selectors, conditional project navigation, compact spacing,
and accessible Services/Logs/trace-span drawers are implemented and pushed at
`a4bcb4c`. The final approved hierarchy uses one content card for
Services/Metrics/Logs/Traces/Settings and sibling cards for Overview/Dashboards/Alerts,
with no nested cards. This is a UI change, not M6.3. Visual approval has been
reported, but the full release gate after the final UI correction and the
M6.2 manual browser acceptance have **not** been reported. See
`UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

**Document status:** V1 implemented through M5; V1 M6 service/infrastructure observability is a proposed next milestone pending its planning and implementation patches. **Canonical implementation evidence:** `ProjectImplementation.md` and the milestone files.

## 1. Product definition

Sentrix is a multi-tenant observability platform for development and operations teams to ingest OpenTelemetry metrics, logs, and traces; investigate project-specific signals; configure metric alerts; and deliver signed webhook notifications. It keeps organization/project policy in Django/PostgreSQL and analytical telemetry in ClickHouse.

**Primary users:** organization owners/admins managing teams; editors configuring projects, credentials, dashboards, alert rules and channels; viewers investigating telemetry without mutation privileges; collectors/SDKs sending telemetry with project credentials.

## 2. Problems addressed

- Collect telemetry using a common, vendor-neutral OTLP/HTTP protocol.
- Keep project data isolated even if an attacker learns a UUID, service name, or trace ID.
- Move from real ingested signals to bounded metrics/log/trace investigations and dashboard panels.
- Detect raw scalar threshold changes and deliver authenticated webhook notifications without putting external HTTP in a user request.
- Provide reproducible Windows/Docker setup, health checks, and operational smoke tests.

## 3. Implemented V1 user journeys

| Journey | V1 outcome | Source |
| --- | --- | --- |
| Sign in | CSRF-protected Django session and current user | `backend/apps/accounts/` |
| Organize | Organization ownership, membership roles, scoped projects | `backend/apps/organizations/`, `backend/apps/projects/` |
| Connect telemetry | Create/revoke scoped project keys; ingest protobuf OTLP metrics/logs/spans | `backend/apps/projects/`, `backend/apps/telemetry/` |
| Investigate metrics | Catalog and scalar-series APIs, 1h–7d explorer | `frontend/src/components/MetricsExplorer.tsx` |
| Explore logs | Bounded severity/text/service/trace filters; raw fields | `LogsExplorer.tsx` |
| Correlate traces | Exact trace lookup, log-to-trace navigation, raw spans | `TraceExplorer.tsx` |
| Pin dashboards | Project-scoped configured metric panels, raw values | `DashboardPanels.tsx` |
| Manage alerts | Scalar threshold rule CRUD, current state, real one-shot evaluation | `AlertsWorkspace.tsx`, `backend/apps/alerts/` |
| Notify | Webhook channels, signed firing/recovered events, durable bounded retries | `backend/apps/alerts/notifications.py` |

V1 does **not** claim automatic recurring evaluation/dispatch: those run through explicit one-shot management commands. Metrics remain raw gauge/sum points, not precomputed rates, percentiles, or SLOs.

## 4. Functional requirements

1. **Organization isolation:** every project belongs to an organization, every browser read checks membership, and mutations enforce backend role checks.
2. **Machine credentials:** raw project key is revealed once, scoped to `telemetry:write`, hashed at rest, revocable/expirable.
3. **OTLP ingestion:** accept binary protobuf over HTTP for all three signals with bounded payloads, optional gzip, and durable ClickHouse acceptance.
4. **Telemetry reads:** project-authorized and tenant-filtered before querying ClickHouse; bound time windows, filters, point counts, and error contracts.
5. **Dashboards:** bounded panels reuse the existing metrics query API; no second value store.
6. **Alerts:** one latest uniquely timestamped scalar point within a configured time window; explicit `pending/ok/firing/no_data/error/disabled` states, no invented recovery on ambiguous/error paths.
7. **Webhooks:** transitions queue only real firing or direct recovery, HMAC-sign payloads, prevent accidental duplicate queueing, allow bounded retry and deny-by-default production egress.
8. **Operability:** health endpoints, schema validation, real OTLP smoke and complete release gate.

## 5. Non-functional requirements and acceptance

- **Security:** no cross-project disclosure; foreign project ID returns not-found; read endpoints never reveal project key or channel signing secret. See `Authentication&Security.md`.
- **Correctness:** durable OTLP 200 only after successful write; missing data ≠ dependency unavailable; no fake metric aggregations or inferred service topology.
- **Bounded workload:** query windows and result limits enforced server-side; rule cap 50 and webhook channel cap 10 per project.
- **Auditability:** code, tests, docs and staged source match exact git baseline; operational verifiers exercise real pathways.
- **Reliability:** ClickHouse outages map to 503 for telemetry; alert errors and webhook retry statuses are explicit.
- **Platform:** Windows 11/PowerShell and Docker Compose acceptance, with Linux/macOS shell bootstrap available.

## 6. Exclusions and later roadmap

**Not implemented in V1 M1–M5:** scheduled alert evaluation/delivery workers, incident management, alert history, service ownership/SLOs, Kubernetes API integration, billing, SSO/MFA, AI root-cause analysis, graph database, unbounded dashboards.

**Proposed V1 M6 sequence:** tenant-scoped service discovery; service workspace; infrastructure/Kubernetes resource attributes; observed trace relationships; operational closeout. This is a plan, **not an existing API/UI**. If the M6 plan patch is accepted, follow `V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md`.

## 7. Release criterion

Do not mark a slice delivered from documentation alone. Require targeted tests, complete `scripts/verify.ps1` gate, applicable live OTLP/browser checks, updated docs, commit/push, and synchronized `main`. Record actual results in `ProjectImplementation.md`.

## 8. V1 milestone coverage through M6

| Stage | Capability | Delivery status | Required proof |
| --- | --- | --- | --- |
| V1 M1 | Identity, organizations/projects, member roles, health and application shell | **Implemented** | Session, CSRF, membership and UI checks |
| V1 M2 | Scoped machine credentials; authenticated OTLP/HTTP; ClickHouse durability | **Implemented** | Real exporter, tenant-bound persistence, failure tests |
| V1 M3 | Raw scalar metrics and configured project dashboard panels | **Implemented** | Query correctness, real metric and browser checks |
| V1 M4 | Log investigation and exact log-to-trace correlation | **Implemented** | Correlated OTLP signals and real navigation |
| V1 M5 | Metric alert evaluation, persisted states and signed webhook delivery | **Implemented** | Firing, deduplication, recovery and delivery closeout |
| V1 M6 | Service discovery, detail, infrastructure attributes and observed span relationships | **M6.1 accepted; M6.2 code pushed/browser gate open** | `2c1b5a2`, `a0e7881`; M6.3–M6.5 planned |

These are **six milestones within product Version 1**, not claims that six separately released product versions exist. M6.1 and M6.2 service UI/API code exists; M6.3–M6.5 are not implemented. For acceptance see `V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md`.

### M6 product acceptance contract (planned)

Users should discover services from a bounded time window of their **own project's** telemetry, investigate a selected service using the existing signals, and view host/Kubernetes labels only when present in actual OTel resource attributes. A service map may connect two services only when an observed parent and child span in the same authorized trace establish the relationship. No automatically inferred health, uptime, dependency, resource existence, or ownership; no Kubernetes API access, SLOs, incident system or background synchronization in M6. Each capability requires a clear no-data, truncated, and dependency-unavailable outcome.

## M6.2 observed Services workspace (code pushed; browser acceptance pending)

Authorized project members browse services from bounded OTLP metrics/logs/spans, selecting
exact service/environment identity (including empty environment), first/last observation,
per-signal counts and bounded metric-name, error-log and trace-ID references from an actual
backend detail API. Generic Metrics/Logs links are not automatically filtered. No inventory,
health, ownership, SLO or inferred dependency is promised. Automated test/release gates
passed; the final operator browser walkthrough remains to be recorded.
