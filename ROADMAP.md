# Sentrix — Product Roadmap (Core Observability Platform)

**Status:** approved direction / planning only. **Baseline reviewed:** GitHub `main` at
`0939cca36f56c6106082976f8a5410ee022e9607` (2026-10-24 review).
This document does not deliver new APIs, workers, collectors, SDKs, integrations,
or monitoring capabilities. Milestone acceptance remains evidence-based.

## North star and positioning

Sentrix should deliver end-to-end observability workflows: connect an
application; collect metrics, logs, traces and infrastructure signals;
discover services; investigate latency, errors and correlations; build
dashboards and alerts; and act on reliable evidence.
The objective is *functional usefulness*, with capabilities supported by real
telemetry and test evidence. Prefer vendor-neutral OpenTelemetry SDKs and
Collector components; build Sentrix-specific components only for real gaps.

**Non-negotiable boundaries:** Django/PostgreSQL control plane for authenticated
accounts, organizations, projects and configuration; ClickHouse telemetry data
plane; Redis only where an explicitly designed worker needs coordination;
project-scoped OTLP/HTTP **protobuf** ingestion with `telemetry:write` key;
session/CSRF access to project read/manage APIs. Browser bundles must not receive
write keys. Tenant authorization precedes any ClickHouse query; limits, retention,
backpressure and costs are part of feature design, not afterthoughts.

## Current implementation and acceptance ledger

| Work | Code state at reviewed baseline | Acceptance state |
| --- | --- | --- |
| V1 M1–M5 | Shipped: sessions/roles/projects, keys, OTLP signals, raw queries, configured dashboards, one-shot alert evaluation, signed webhooks | Historical milestone release evidence in the repository |
| V1 M6.1 | Service catalog from stored telemetry | Previously accepted |
| V1 M6.2 | Services workspace and bounded exact service detail, shipped | Manual browser/foreign-user/real exporter evidence still open in `M6_2_BROWSER_ACCEPTANCE.md` |
| V1 M6.3 | Infrastructure resource-attribute discovery and workspace, shipped in `75d2d21`; framework docs/sidebar shipped in `0939cca` | Full automated gate reported: 182 backend tests and 58 frontend tests; operator IR-001–IR-008/browser acceptance still open |
| V1 M6.4 | Observed cross-service relationship map | Not implemented; do not start before M6.2/M6.3 closeout |
| V1 M6.5 | Real external telemetry, multi-service operational proof and V1 M6 closeout | Not implemented |

The counts above are **previous operator reports**, not tests run by this roadmap
change. Historical headings that describe M6.3 as a 'candidate' are superseded
by this ledger; they do not undo the pushed implementation. None of this asserts
that production use, all four framework recipes, or manual acceptance is proven.

## First-time user journey (success criterion)

1. Create/select an authorized organization and project.
2. Choose the runtime: Laravel/PHP, Node.js, Next.js (server), Django/Python,
   Docker or OpenTelemetry Collector. React/browser apps must instrument an
   existing backend until a dedicated safe browser ingestion design exists.
3. Create a project-scoped key and store the one-time secret **server-side**.
4. Copy an SDK/collector configuration whose endpoint follows the **exporter's**
   network context: Windows host, Compose service or remote HTTPS deployment.
5. Generate an actual request or workload and export real OTLP protobuf.
6. See a truthful received/not-received result, service identity and timestamp;
   get actionable diagnostics for auth, wire format, connectivity and storage.
7. Investigate traces, logs, metrics, infrastructure and alerts in the **same**
   authorized project, with no invented health or topology.

Do not confuse an in-app help page, synthetic demo rows or successful local
unit tests with a working framework integration or an actual live connection.

## Ordered near-term milestones — finish V1 M6 first

### Gate A — M6.2 / M6.3 acceptance closeout (current priority)

- Run browser/keyboard/mobile and real OTLP integration checks recorded in
  `M6_2_BROWSER_ACCEPTANCE.md` and `M6_3_BROWSER_ACCEPTANCE.md`.
- Verify independent users and projects, foreign 404 before data queries,
  observed host/Kubernetes attributes, empty/error/truncated states and switching.
- Verify framework onboarding sidebar and **server-only** secret handling.
- Record operator, date, tested SHA, sample identities (never keys), results,
  failures and remediation. Update milestone/test docs with observed outcomes.
- Run full `scripts/verify.ps1`, commit and push only an actually accepted closeout.

### V1 M6.4 — Observed service relationships (blocked)

- Build bounded edges from real parent/child spans across service boundaries in
  the **same trace and tenant**. Preserve exact environment, first/last observed
  and supporting spans; do not fill absent edges or infer network topology.
- Add authenticated backend queries, frontend service-map exploration and
  tenant/negative/partial-trace tests. No graph database without evidence.

### V1 M6.5 — Service/infrastructure operational closeout (blocked)

- Use a real exporter producing multi-service traces, metrics/logs and host/K8s
  resource attributes; verify browser and API behavior, isolation, truncation,
  ingest failure/retry semantics and clean teardown of temporary fixtures.
- Complete full release gate, acceptance records, synchronized docs and clean
  GitHub `main` before starting a new numbered feature milestone.

## Post-M6 roadmap (proposed; NOT implemented)

Milestone numbers below are **planning labels**, not approved delivery dates or
software releases. Define a scoped spec + testing plan before implementing each.

| Order | Planned milestone | Minimum capability | Required proof |
| --- | --- | --- | --- |
| M7 | Guided integrations and verified onboarding | Versioned Laravel/PHP, Node/Express, Next.js Node, Django/Python, container and OTel Collector recipes; context-safe env examples; connection diagnostics and first-telemetry test | Live exporter per supported stack; secrets never exposed in browser; tenant/isolation and 401/403/415/503 paths |
| M8 | Application Performance Monitoring | RED measures, span latency and error analysis, trace waterfall and logs-in-context, service dependencies only from observed spans | Reproducible traces with known latency/error status; mathematically valid aggregations, sample counts and time windows |
| M9 | Host and Kubernetes signal collection | Official Collector receivers for host/container/K8s attributes, deployment playbooks, source/receiver health and resource views | Live host and cluster acceptance; least-privilege collection; no 'healthy' inventory inferred from historical attributes |
| M10 | Querying, dashboards and telemetry economics | Aggregated rates/percentiles where semantically valid, flexible filters, dashboard composition, retention/cardinality/query budgets | Reference datasets, bounded queries, tenancy, performance tests and transparent missing-data handling |
| M11 | Continuous alerting and SLO workflows | Explicitly scheduled evaluations and delivery workers, histories, dedupe, silences, service objectives and error budgets | Durable restart/retry/recovery proofs, no duplicate notifications, time correctness and no fabricated SLOs |
| M12 | Browser/mobile and incidents (separate scoped slices) | Safe browser-specific ingestion/auth, browser errors/performance, incident workflows and integrations | Browser public-token threat model, CORS/abuse limits, retention/privacy/security review and end-to-end production-like tests |
| Cross-cutting | Production readiness | Auth hardening/SSO where needed, deployment, backup/restore, migrations, uptime, resource limits, monitoring of Sentrix itself | Restore drill, load/security test, upgrade/rollback rehearsals, documented SLO and operating runbooks |

Dependencies: do not claim an agent, Kubernetes watcher, distributed collector,
RUM SDK, scheduled worker, reliable percentile, current node health, SLO,
incident feature, or API-key-based control-plane access until code and live
acceptance actually establish it. Preserve an explicit `planned` label in docs/UI.

## Definition of done for every future milestone

1. Confirm exact GitHub `main` SHA and a clean user checkout; use a tested
   `git apply --check` patch with code, tests and all materially affected docs.
2. Define contracts and threats first: tenant scope, trust boundary, wire format,
   permissions, error states, retention/cardinality and query/workload limits.
3. Run targeted backend/frontend tests, then the complete Windows/Docker
   `scripts/verify.ps1` gate (pytest, Ruff, mypy, Django/schema, ESLint,
   TypeScript, Vitest and production build).
4. Run real instrumented application/Collector and browser acceptance for any
   advertised new feature. Record tested SDK versions, endpoint, environment,
   nonsecret fixture IDs, operator/date, failures and expected observations.
5. Update `README.md`, `PRD.md`, `ARCHITECTURE.md`, `ProjectImplementation.md`,
   active milestone/testing plans and any affected API/DB/security/integration,
   setup/design/debug docs. Review all handbook areas as `AGENTS.md` requires.
6. Commit and push the accepted slice; verify `HEAD == origin/main` and a
   clean tree. No subsequent milestone from an unaccepted implementation.

## Documentation and UI policy

Keep **Documentation** in the sidebar. Lead with framework quickstarts and
getting-started steps, not the API reference. Preserve the hidden direct API
reference route until it is ready to surface deliberately. Each runnable guide
needs prerequisites, secrets/endpoint selection, install, configure, request,
verify and troubleshooting. Upstream SDK and protocol references are learning sources,
not proof that a Sentrix integration has been exercised.

**Canonical status:** this roadmap and the latest evidenced entry in
`ProjectImplementation.md`; detailed V1 M6 contracts live in
`V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md`. Acceptance checklists
remain authoritative for unverified browser and real-world behavior.
