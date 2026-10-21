# Sentrix — Project Implementation Register

## M6.2 pushed implementation and demo fixture checkpoint (2026-10-21)

Actual `main` SHA verified locally and remotely: `a0e78817749e6a235194cb71d5a9349e4e9844b9`
(`feat(services): complete M6.2 service workspace and detail`). The Windows/Docker
`./scripts/verify.ps1` release gate passed: 164 backend tests, 44 frontend tests, Ruff
lint/format, mypy (99 files), Django checks, ClickHouse schema, TypeScript and Vite build.
The working tree was clean and synchronized after push. **Manual browser acceptance has not
been reported yet.** Historical provisional M6.2 paragraphs below predate this commit.
The opt-in `seed_demo` management command is an **unverified change pending host tests**,
not a released milestone or a substitute for real telemetry acceptance. See `DEMO_SEEDING.md`.
M6.3 remains gated on confirmed M6.2 manual/browser/documentation acceptance.

## M6.2 correction staging (not accepted yet)

The first M6.2 patch was applied cleanly at the M6.1 `2c1b5a2` baseline. An additional M6.2
patch stages a tenant-authorized detail API, bounded metric/error-log/trace references, and React
query/UI/test integration. Earlier notes describing only an aggregate detail panel apply to the
initial candidate, not this correction. Do not mark M6.2 implemented or proceed to M6.3 until
focused tests, the complete release gate, browser acceptance, commit, push, and clean main are proven.

**Canonical repository:** `https://github.com/mooskyai/sentrix`
**Last independently confirmed clean/pushed SHA:** `2c1b5a2c18d1929b37ff0a55796eaceb41070592` (`feat(services): add tenant-scoped service catalog foundation`).
**Current slice:** M6.1 complete/pushed; M6.2 Services workspace implementation prepared against `2c1b5a2` and **awaiting user test/browser acceptance**. M6.3–M6.5 remain planned.

## 1. Milestone implementation status

| Milestone | Outcome | State | Evidence |
| --- | --- | --- | --- |
| V1 M1 | Django/React control plane, auth, org/project tenancy, roles, health, visual foundation | Implemented | `V1_MILESTONE.md`, `V1_MILESTONE_TESTING.md` |
| V1 M2 | project API keys, OTLP/HTTP protocol + durable ClickHouse storage; real trace smoke | Implemented | `V1_M2_MILESTONE*.md`, `scripts/verify-m2.ps1` |
| V1 M3 | bounded scalar metrics queries, Metrics explorer, dashboard panels, real metric smoke | Implemented | `V1_M3_MILESTONE*.md`, `scripts/verify-m3.ps1` |
| V1 M4 | bounded log search, Logs explorer, exact trace lookup/navigation, operational smoke | Implemented | `V1_M4_MILESTONE*.md`, `scripts/verify-m4.ps1` |
| V1 M5 | metric rules/current evaluation state, Alerts workspace, signed webhook channels/delivery, real OTLP + browser smoke | **Complete / pushed** | `V1_M5_MILESTONE*.md`, `scripts/verify-m5.ps1`; `d43947a` |
| V1 M6 | service catalog, detail, host/K8s resource discovery, observed service relationships, operational closeout | **M6.1 delivered; M6.2 awaiting acceptance** | `2c1b5a2`, `V1_M6_MILESTONE*.md` |

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

Complete M6.2 frontend and real-browser acceptance against `2c1b5a2`: focused React tests, full release gate, Services page tenant switching and accurate empty/truncated states. Only then commit/push and begin M6.3.

## 6. V1 M6 detailed implementation ledger — live

The M6 plan is delivered one accepted slice at a time. M6.1 is committed; M6.2 is under implementation and remains unaccepted until the full gate and browser smoke. Future slices remain planned.

| Slice | Deliverable | Current status | Must prove before commit |
| --- | --- | --- | --- |
| M6.1 | Authorization-first, bounded multi-signal service catalog API | **Completed/pushed** `2c1b5a2` | 15 focused tests, 150 backend and 35 frontend full gate; real OTLP tenant isolation |
| M6.2 | Services list/detail browser and correlation links | **Pending acceptance** | Real browser project switching, window/query keys and no synthesized stats |
| M6.3 | Host/Kubernetes attribute-based resource views | **Planned** | Exact attribute evidence and partial/missing-attribute behavior |
| M6.4 | Cross-service observed parent/child span relationships | **Planned** | Positive matched parent/child joins and no false edge cases |
| M6.5 | End-to-end operational proof, docs and closeout | **Planned** | Real OTLP, tenant isolation, browser acceptance, full release gate |

The planning docs were committed in `39bb7f7`; the first implementation slice M6.1 was accepted and pushed as `2c1b5a2`. All further slices require the same test, documentation, commit and clean-branch gates.

## V1 M6.1 — service catalog foundation (accepted and pushed)

Baseline: `39bb7f7ff99fc42fc5b55fb5b4f7030bcbf8380f`, confirmed clean/pushed.
Implementation patch: session-authenticated, tenant-first bounded catalog query across existing OTLP
metrics/logs/spans with typed ClickHouse parameters, exact identity merge and explicit truncation.
No models, schema changes, background scheduler, or UI. Focused tests include mocked ClickHouse and
real multi-tenant OTLP ingestion. **Accepted:** 15 focused tests, 150 backend and 35 frontend tests,
Ruff/mypy/Django/ClickHouse checks and frontend production build green on the Windows/Docker host.
Committed/pushed at `2c1b5a2`, clean `main`. M6.2 can proceed.

Docs reviewed: PRD (scope already agreed), DESIGN (no UI), ARCHITECTURE (updated), DATABASE (updated),
API (updated), AGENTS (rules preserved), README (updated), this register (updated), Setup (no new env),
FeatureDevelopment (updated), Authentication&Security (updated), Integrations (unchanged OTLP),
Testing&QA (updated), Debugging (no new operational procedure).

## V1 M6.2 — Services workspace (implementation awaiting acceptance)

Baseline `2c1b5a2c18d1929b37ff0a55796eaceb41070592`, pushed clean by the user.
M6.2 proposes an authenticated browser Services workspace and exact service/environment detail read
from the already verified M6.1 aggregate catalog. The UI shows bounded counts and observed first/last
UTC timestamps; it does **not** introduce a separate detail query endpoint, metric-name summary,
recent error log references, or trace-ID discovery. Explorer links retain the project and explicitly
require the operator to apply supported filters/trace IDs at their destination.

Frontend React Query keys include immutable project UUID, window bounds, and catalog limit. Project
navigation remounts Services for tenant isolation; selected identities are mere URL query parameters,
not authorization credentials. Empty environment is displayed explicitly; absence of observations
is not a claim of deletion/down status. Truncated catalogs are not treated as complete.

**Acceptance pending:** focused ServicesWorkspace tests, frontend lint/typecheck/build, full
`scripts/verify.ps1`, real browser smoke with observed telemetry/project switching, staged doc review,
commit/push/clean main. No source/backend schema or ingestion changes are proposed.

Docs reviewed: PRD (unchanged requirements), DESIGN (updated), ARCHITECTURE (updated), DATABASE
(no schema change), API (updated client consumption), AGENTS (standing rules unchanged), README
(updated), ProjectImplementation (updated), Setup (no new setup), FeatureDevelopment (updated),
Authentication&Security (unchanged authorization), Integrations (unchanged OTLP/webhook), Testing&QA
(updated), Debugging (no new failure family). M6.3 remains blocked until M6.2 acceptance and push.
