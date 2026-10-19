# Sentrix — Project Implementation Register

**Canonical repository:** `https://github.com/mooskyai/sentrix`
**Last independently confirmed clean/pushed SHA:** `39bb7f7ff99fc42fc5b55fb5b4f7030bcbf8380f` (`docs: establish V1 M1-M6 project documentation foundation`).
**Current slice:** M6.1 service catalog API and tests drafted against `39bb7f7`; acceptance, commit and push pending. M6.2–M6.5 remain planned.

## 1. Milestone implementation status

| Milestone | Outcome | State | Evidence |
| --- | --- | --- | --- |
| V1 M1 | Django/React control plane, auth, org/project tenancy, roles, health, visual foundation | Implemented | `V1_MILESTONE.md`, `V1_MILESTONE_TESTING.md` |
| V1 M2 | project API keys, OTLP/HTTP protocol + durable ClickHouse storage; real trace smoke | Implemented | `V1_M2_MILESTONE*.md`, `scripts/verify-m2.ps1` |
| V1 M3 | bounded scalar metrics queries, Metrics explorer, dashboard panels, real metric smoke | Implemented | `V1_M3_MILESTONE*.md`, `scripts/verify-m3.ps1` |
| V1 M4 | bounded log search, Logs explorer, exact trace lookup/navigation, operational smoke | Implemented | `V1_M4_MILESTONE*.md`, `scripts/verify-m4.ps1` |
| V1 M5 | metric rules/current evaluation state, Alerts workspace, signed webhook channels/delivery, real OTLP + browser smoke | **Complete / pushed** | `V1_M5_MILESTONE*.md`, `scripts/verify-m5.ps1`; `d43947a` |
| V1 M6 | service catalog, detail, host/K8s resource discovery, observed service relationships, operational closeout | **M6.1 in progress; M6.2–M6.5 planned** | `V1_M6_MILESTONE*.md`, M6.1 code/tests awaiting gate |

## 2. Verified M5 closing evidence

- Real OTLP scalar metric drove a `firing` alert, signed HTTP 204 webhook, same-state no duplicate, and real `ok` recovery + signed webhook.
- Foreign tenant API attempts returned 404; manual browser verification showed the temporary alert in `ok`.
- Verification removed temporary PostgreSQL fixtures and receiver state, preserving ClickHouse telemetry and persistent volumes.
- Full M5 gate: 135 backend tests, 35 frontend tests, Ruff, mypy, Django/migrations, ClickHouse validation, frontend lint/typecheck/production build all passed on the acceptance environment.
- M5 completion `d43947a` pushed; `main` matched `origin/main`. These counts are **historical evidence**, not promises for future runs.

## 3. Implementation principle

For each slice maintain: baseline SHA; scope/acceptance; code and migration/schema changes; documented trust boundaries; tests; real operational/browser proof where required; application/verification commands; resulting commit SHA; push and clean status. **An uncommitted patch is not a delivered milestone.**

## 4. New change record template — mandatory for every slice

```text
### <milestone> — <short name>
Status: Planned | In progress | Blocked | Verified | Committed and pushed
Baseline SHA: <exact git rev-parse HEAD before edits>
Scope: <user-visible and internal behavior>
Files changed: <source/tests/docs/migrations>
Security/tenant review: <auth, RBAC, scope, secrets, error contracts>
Automated checks: <exact commands and observed results>
Operational/browser checks: <real run and observed results; or N/A with rationale>
Docs reviewed: PRD, DESIGN, ARCHITECTURE, DATABASE, API, AGENTS, README,
  ProjectImplementation, Setup, FeatureDevelopment, Authentication&Security,
  Integrations, Testing&QA, Debugging; note each material change
Commit SHA / remote status: <actual values, not intent>
Next slice: <gated next step>
```

## 5. Current next action

Establish these 14-document references without overwriting existing `README.md` or `ARCHITECTURE.md`; validate the patch on the exact local tree and against any outstanding M6 planning patch. Following accepted documentation commit, begin **M6 planning acceptance** if not yet applied; only then M6.1 implementation. Never assume M6 APIs or UI already exist.

## 6. V1 M6 detailed implementation ledger — planned

The M6 documents define the next five ordered slices but **do not** introduce production code. Update this ledger only with real completed evidence; planned work stays planned until applied and verified.

| Slice | Deliverable | Current status | Must prove before commit |
| --- | --- | --- | --- |
| M6.1 | Authorization-first, bounded multi-signal service catalog API | **Planned** | Real two-tenant ClickHouse isolation and honest empty/error semantics |
| M6.2 | Services list/detail browser and correlation links | **Planned** | Real browser project switching, window/filter/query keys and no synthesized stats |
| M6.3 | Host/Kubernetes attribute-based resource views | **Planned** | Exact attribute evidence and partial/missing-attribute behavior |
| M6.4 | Cross-service observed parent/child span relationships | **Planned** | Positive matched parent/child joins and no false edge cases |
| M6.5 | End-to-end operational proof, docs and closeout | **Planned** | Real OTLP, tenant isolation, browser acceptance, full release gate |

Once the V1 M6 planning patch is applied, `V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md` become the detailed roadmap and test matrix. This is a *documentation* checkpoint until a user-verified commit confirms otherwise. The first technical implementation slice begins only after the documentation baseline is committed, pushed and clean.

## V1 M6.1 — service catalog foundation (awaiting verification)

Baseline: `39bb7f7ff99fc42fc5b55fb5b4f7030bcbf8380f`, confirmed clean/pushed.
Implementation patch: session-authenticated, tenant-first bounded catalog query across existing OTLP
metrics/logs/spans with typed ClickHouse parameters, exact identity merge and explicit truncation.
No models, schema changes, background scheduler, or UI. Focused tests include mocked ClickHouse and
real multi-tenant OTLP ingestion. **Checks not yet executed on the user's acceptance host.** Before
closing: targeted pytest/Ruff/mypy, real ClickHouse verification, full `verify.ps1`, review staged
docs and code, commit/push and confirm clean main. M6.2 remains blocked until then.

Docs reviewed: PRD (scope already agreed), DESIGN (no UI), ARCHITECTURE (updated), DATABASE (updated),
API (updated), AGENTS (rules preserved), README (updated), this register (updated), Setup (no new env),
FeatureDevelopment (updated), Authentication&Security (updated), Integrations (unchanged OTLP),
Testing&QA (updated), Debugging (no new operational procedure).
