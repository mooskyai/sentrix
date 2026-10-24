# Sentrix — Product Requirements Document

## Product direction, evidence and phased scope — current 2026-10-24

**North star:** connected applications deliver real telemetry that developers
can investigate across Services, Traces, Logs, Metrics, Infrastructure, dashboards
and alerts. Prioritize evidence-backed core observability workflows, not
visual imitation or unsupported claims. Prefer OpenTelemetry SDKs/Collector
and first-class, tested onboarding.
**[ROADMAP.md](ROADMAP.md)** is the ordered product plan and release-gate ledger.

**At `0939cca`:** V1 M1–M5 and M6.1 have existing delivery evidence. M6.2
service detail and M6.3 infrastructure/API plus Documentation sidebar, Laravel,
Node.js, React and Next.js guide code are pushed. The operator reported a full
182-backend/58-frontend automated gate; real framework certification and
M6.2/M6.3 manual browser acceptance are still open. M6.4 and M6.5 are planned.

**Future requirements, not existing features:** reliable guided real-exporter
onboarding (including Django/Collector), evidence-backed APM analysis and service
relationships, host/K8s collection, enhanced aggregate/query/dashboards,
continuous alert scheduling/SLOs, and safely scoped browser monitoring. Each
requires its own protocol/security/error/limit contract and test evidence.

## Historical M6.3 requirement brief (code now pushed; manual acceptance open)

M6.3 candidate user story: a signed-in project member can inspect observed host/Kubernetes
resource dimensions derived from ingested OTLP, including co-observed names, last seen and counts.
It must not advertise live cluster inventory, resource status or topology. M6.2 manual browser
acceptance remains open; M6.3 operator acceptance is separate and unreported.

## Pre-M6.3 UI refinement — committed; final acceptance pending

The shared right-side header selectors, conditional project navigation, compact spacing,
and accessible Services/Logs/trace-span drawers are implemented and pushed at
`a4bcb4c`. The final approved hierarchy uses one content card for
Services/Metrics/Logs/Traces/Settings and sibling cards for Overview/Dashboards/Alerts,
with no nested cards. This is a UI change, not M6.3. Visual approval has been
reported; the full release gate after the final UI correction passed on
2026-10-22 (170 backend and 50 frontend tests). M6.2 manual browser
acceptance has **not** been reported. See
`UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

**Current document status:** M6.2/M6.3 code is pushed; real operator/browser acceptance is still open. M6.4/M6.5 remain planned. See `ROADMAP.md`, `ProjectImplementation.md` and the M6 acceptance checklists.

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

**V1 M6 current sequence:** tenant-scoped service discovery, Services detail and observed infrastructure attributes have implementation evidence. M6.2/M6.3 manual acceptance remains open; only then proceed to M6.4 real-span relationship mapping and M6.5 operational closeout. Follow `ROADMAP.md`, `V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md`.

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
| V1 M6 | Service discovery/detail and observed infrastructure attributes; service map planned | **M6.1 accepted; M6.2/M6.3 code pushed, manual acceptance open** | `75d2d21`, `0939cca`; M6.4–M6.5 planned |

These are **six milestones within product Version 1**, not six separately released product versions. M6.2 and M6.3 code is shipped, but manual acceptance remains unrecorded; M6.4/M6.5 are unimplemented. See `ROADMAP.md` and the M6 milestone/testing/acceptance docs.

### M6 product acceptance contract (planned)

Users should discover services from a bounded time window of their **own project's** telemetry, investigate a selected service using the existing signals, and view host/Kubernetes labels only when present in actual OTel resource attributes. A service map may connect two services only when an observed parent and child span in the same authorized trace establish the relationship. No automatically inferred health, uptime, dependency, resource existence, or ownership; no Kubernetes API access, SLOs, incident system or background synchronization in M6. Each capability requires a clear no-data, truncated, and dependency-unavailable outcome.

## M6.2 observed Services workspace (code pushed; browser acceptance pending)

Authorized project members browse services from bounded OTLP metrics/logs/spans, selecting
exact service/environment identity (including empty environment), first/last observation,
per-signal counts and bounded metric-name, error-log and trace-ID references from an actual
backend detail API. Generic Metrics/Logs links are not automatically filtered. No inventory,
health, ownership, SLO or inferred dependency is promised. Automated test/release gates
passed; the final operator browser walkthrough remains to be recorded.
