# Sentrix — Feature Development Playbook

## Pre-M6.3 UI refinement (pending acceptance)

Against clean pushed `8b8d3fd`, the application shell consolidates organization/project
selection into the header; project links are withheld until both valid selections exist, and
Services/Logs/Trace span inspection uses a right drawer. Compact spacing is a presentation
change only. Validation and operator steps are recorded in `UI_DENSITY_AND_DRAWERS.md`.
Do not treat this proposal as passed, committed or a new infrastructure milestone until the
full release gate, browser acceptance and clean push are documented.

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
