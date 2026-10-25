# Sentrix — Feature Development Playbook

## M7.1 first-telemetry candidate workflow

Implement a narrow read-only diagnostic before broader integration helpers.
Test project membership before any ClickHouse query, explicit 24h window,
three typed signal queries, empty vs 503, and browser read-only/refetch states.
Run focused/backend/frontend/full gate; then record real OTLP/operator proof
before any acceptance. Updating documentation and master checklist is required.
Do not infer exporter health from stored historical samples.

## M6 live operator smoke tool — release gate preparation

`backend/scripts/m6_acceptance_smoke.py` sends genuine OTLP/HTTP protobuf in a
separate process with one parent/child chain and matched logs/metrics/resource
attributes. Tests cover payload parentage, allowed TLS/loopback origins, secret
handling and sanitized transport failures. See `docs/M6_ACCEPTANCE_PRODUCER.md`;
operator browser/foreign-user checks and external application instrumentation
must still be recorded independently. Do not start the M6.5 feature slice from
this tool's presence alone.

## Global workspace selection maintenance — candidate

Use `workspacePersistence.ts` to reconcile server-listed organization/project
IDs with a versioned per-user localStorage preference. Do not introduce
provider-independent storage keys, client-side authorization, or hidden fallback
from an unauthorized explicit project route. Preserve the ability to create a
new organization (refresh membership before selecting it) and to select the
first project after project creation. Test with two users, missing/stale IDs,
new/empty organizations, reloads and blocked browser storage.

## M6.4 implementation contract — candidate

For relationship reads, authenticate project first, parameterize both tenant
UUIDs, use UTC half-open bounded windows and fixed raw scan limits, and resolve
an edge only when observed parent/child span IDs belong to the same trace.
Group exact service/environment pairs; deduplicate retry spans; expose evidence
and truncation in the API/UI. Update focused tests and operational checklists;
do not advance acceptance from synthetic fixtures or unit tests alone.

## Implementation workflow for roadmap items — 2026-10-24

Use [ROADMAP.md](ROADMAP.md) to select one **unblocked** milestone; start with
an exact GitHub baseline, review affected backend/frontend code, specify user
journey and network/security/tenant contracts. For a framework integration,
validate a real process-exporter path, logs/metrics/traces signal support,
secret handling and a truthful verification result before calling it supported.

Preserve the existing documentation sync and `scripts/verify.ps1` release
gate. Add positive, negative, error, project switch and real external signal
tests plus browser acceptance. Update current milestone/test docs and
`ProjectImplementation.md`; commit and push only after evidence is recorded.

## Historical framework-doc implementation checklist

Keep framework examples tied to the actual `/v1/traces`, `/v1/metrics`, `/v1/logs`
protobuf ingestion boundary. Test framework switching, sidebar access for authenticated
users without a project, and removal of visible API-reference navigation links.
React/Next browser bundles must never contain telemetry write credentials.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 candidate follows the existing service-catalog pattern: project membership lookup in DRF,
trusted UUIDs, typed bounded ClickHouse query over preserved Map attributes, browser query keys
including project/window, and a single-level Infrastructure page. The server returns complete
co-observed attribute sets rather than joining independent names into a topology. No new model,
collector or Kubernetes integration.

## Pre-M6.3 UI refinement — pushed; final acceptance pending

The compact header selectors, authorized project navigation and detail drawers are
implemented and visually approved. The final single-level card correction was committed
and pushed at `a4bcb4c`. The post-correction `scripts/verify.ps1` gate passed
on 2026-10-22 (170 backend, 50 frontend tests). Manual M6.2 browser
acceptance remains unreported. M6.3 stays blocked until it is recorded and
the closeout documentation is committed and pushed.
See `UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

## Opt-in demo fixture development rule

`apps.telemetry.management.commands.seed_demo` creates clearly marked synthetic
M1–M6.2 fixtures only, using the existing authorized project/OTLP ingest boundaries.
It must not be used as proof of production telemetry, service health, infrastructure
inventory or the M6.2 real-browser acceptance. See `DEMO_SEEDING.md` and tests.

## V1 M6.1 implementation slice

Introduce the service query helper and Django read view in `apps.telemetry`, register the
project-scoped catalog route, and add focused tests including a live three-signal OTLP test. Keep
service-name and environment strictly as observed. No frontend Services screen in M6.1; that is M6.2.
Review the entire handbook, update affected references in the same patch, and wait for focused/full
green checks and a clean pushed commit before starting M6.2.

**Audience:** developers and coding agents implementing scoped V1+ slices. Core coding constraints: `CODING_GUIDELINE.md`; enduring rules: `AGENTS.md`.

## 1. Slice lifecycle

1. Read `git status -sb`, `git rev-parse HEAD`, relevant API/view/model/test files and active milestone plan.
2. Specify the user outcome, exact acceptance/negative tests, tenant roles, failure behavior, operational evidence and out-of-scope boundaries.
3. Choose the existing boundary to extend, not a parallel data path. Update relevant docs **inside** the feature patch.
4. Implement with tests for successes, malformed input, foreign UUID, viewer role, ClickHouse failure, truncated/empty states, and stale writes as relevant.
5. Run focused gates then full `scripts/verify.ps1`; run real OTLP/browser acceptance when the slice requires it.
6. Inspect `git diff --check`, status, staged stat; commit one accepted slice and push. Require clean synced `main` before next.

## 2. Backend patterns

- Django app ownership: `accounts`, `organizations`, `projects`, `telemetry`, `alerts`, `common`.
- Routes in app `urls.py`; session view resolves membership-scoped project before any child resource or data-plane client is fetched.
- Use serializers/typed validation for bounded windows, UUID/trace ID grammar, finite numbers and limits; write tests for negative cases.
- Project-scoped writes require owner/admin/editor; viewer reads only; never infer RBAC from the frontend.
- Config and operational state are PostgreSQL; metrics/logs/spans remain ClickHouse, with tenant-first predicates and typed parameters.
- Use Django migration files for relational schema and the separate ClickHouse command for telemetry DDL.
- Background one-shot evaluator and dispatcher do not run from browser/API requests; no hidden cron dependency.

## 3. Frontend patterns

- Prefer existing `/orgs/:organizationSlug/projects/:projectSlug/:section` workspace context and component APIs.
- New query keys include immutable project UUID and all applied filters. Project switch must remount/invalidate relevant state.
- Raw telemetry semantics matter; no extra rollups/rates, service health, or topology without proven model semantics.
- Display loading/empty/error/truncated and viewer read-only modes. Handle network failures explicitly.
- Add focused React Testing Library/Vitest tests for new behavior including error and role boundaries.
- Visual components reuse `frontend/src/theme.css` and shared semantic utilities.

## 4. Feature-specific acceptance examples

| Feature domain | Required behavior |
| --- | --- |
| Credentials | creation secret once, safe metadata later, revocation, machine vs session isolation |
| OTLP | official protobuf, scope auth, 200 only after durable persistence, 503 on sink unavailable |
| Metrics | raw scalar only, tenant/time/window/limits, no histogram flattening |
| Logs/traces | exact correlation ID validation, raw attributes/parentage, no fake topologies |
| Dashboards | bounded project config, panel series from existing API, no sample copies |
| Alerts | latest unique scalar point, explicit statuses, stale-evaluation protection |
| Webhooks | egress allowlist, signed canonical body, durable lease/retry, bounded error codes |
| Proposed M6 | service and infrastructure discovery from OTLP only; bounded and evidence-backed |

## 5. PR/patch description template

```text
Baseline: <exact SHA>
Scope & out-of-scope: ...
Data/auth/API/UI impact: ...
Source changes + new files: ...
Tests, security/tenancy negatives: ...
Docs reviewed/updated: ...
Migration/schema impact: ...
Operational/browser proof: ...
Risk/rollback: ...
Commit/push/clean branch: ...
```

## 6. Documentation update rule

Review the **entire 14-file set** in `AGENTS.md` for every development change. Update material sections together with source/tests. In every implemented slice append a verified entry to `ProjectImplementation.md` and refresh `README.md` overview/setup/feature pointers; preserve the milestone-specific docs. Never change docs merely to signal a pass: record exact commands/output as evidence.

## M6 development sequence and documentation gates

| Slice | Implementation boundary | Documentation to sync at the same time |
| --- | --- | --- |
| M6.1 | Project-scoped service catalog/queries | `API.md`, `DATABASE.md`, `ARCHITECTURE.md`, `Testing&QA.md` |
| M6.2 | Services workspace/detail | `DESIGN.md`, `PRD.md`, `API.md`, `Testing&QA.md` |
| M6.3 | Resource dimensions from real OTLP attributes | `DATABASE.md`, `Integrations.md`, `Authentication&Security.md` |
| M6.4 | Observed trace parent/child relationships | `ARCHITECTURE.md`, `API.md`, `DESIGN.md`, `Debugging.md` |
| M6.5 | Real OTLP/UI closeout | `Setup.md`, `Testing&QA.md`, `README.md`, milestone testing, implementation ledger |

This table is the minimum review routing, not an exemption for the other handbook documents. Check all fourteen at every slice. A planned design is not executable behavior; do not add fake inventory/health values or a second telemetry store. Continue code → targeted tests → full gate + necessary real smoke → docs and security review → commit → push → clean branch, one slice at a time. See `V1_M6_MILESTONE.md`.

## V1 M6.2 Services workspace development slice

Use M6.1 aggregate types in `frontend/src/types.ts` and `getServiceCatalog` in the shared API client.
Register `services` in the project workspace route/section map and sidebar, and remount on project
changes. Query keys must include project UUID, exact UTC start/end and limit. Detail is a selected
catalog row (not an independently queried service entity). Accept empty environment as legitimate.
Use explicit failure/empty/truncation UI and disclosure that existing explorer links do not prefilter.
Ship component/browser tests, then the complete repository release gate before commit.

## Linked documentation workflow

Keep the existing Settings API-key UI as the entry point: show **Telemetry setup guide** and **API reference** as ordinary links for viewers and writers. Register the two documentation routes in the existing authenticated app router, not in `WORKSPACE_SECTIONS` or the global project navigation. Maintain the checked-in guides and the UI pages with the real backend API/OTLP contracts, then run component/page tests and the full gate.
