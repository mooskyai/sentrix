# Sentrix — Project Implementation Register

## M7.2 — guided server integration candidate (2026-10-25)

Baseline `4116f087127575a8218d85708932ef1448262361` (M7.1 committed,
local 233-backend/87-frontend full gate reported). This slice introduces a
Settings guide for Django/Python and Node.js/Express, validated host/Compose/
remote-HTTPS origins, safe resource identity inputs and server-only placeholder
commands. The follow-up check uses the authorized project's existing bounded
Services catalog (`limit=500`, last 24h); it distinguishes exact observed
service/environment, missing data, truncated results and dependency failures.
Unit/component tests cover safety, read isolation, no secret entry, refresh and
error states. **Candidate:** run the full gate and actual operator/browser
verification; no framework-runtime certification or M6/M7.1 sign-off implied.

## M7.1 — first-telemetry diagnostics implementation candidate (2026-10-25)

GitHub baseline: `16c94afdbbc5d5cfaf107760d3559ecc795d6143`, clean
`main` as operator-reported. This patch adds a project-session, member-only
observation endpoint, on-demand Settings panel and negative tests for foreign
users, empty data, invalid read-back and query failure. Django derives tenant
IDs from membership before ClickHouse; browser receives no ingestion secrets.
**Not yet executed on operator Compose:** focused tests, full `verify.ps1`,
real first-telemetry smoke, browser review, CI, commit/push. M6 manual
acceptance and M7.1 live onboarding sign-off both remain open. Check
`V1_M7_MILESTONE_TESTING.md` and the master checklist before acceptance.

## M1–M12 master acceptance index — documentation-only candidate (2026-10-25)

Added `MILESTONE_ACCEPTANCE_CHECKLIST.md` as the evidence index for historical
M1–M5 and M6.1, detailed M6.2–M6.5 closeout gates, and explicitly **planned**
M7–M12. Baseline is pushed `61161bd3fb2da859ac1f6636a71e5daccbff6e02`;
its GitHub Actions succeeded at
https://github.com/mooskyai/sentrix/actions/runs/40162534351.
Operator-reported read-back passed for run
`319b34b2346645fe8729b5518ca8a236`, trace
`29b8393d3bef43d191ebc371b0113e26` in project
`07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`, with the previously reported
224-backend/82-frontend release gate. Browser/independent-user/real app,
retries, credential revocation and closeout sign-off remain **unverified**.
This checklist patch changes documentation only; run the repository gate and
record its actual result before a follow-up documentation commit/push.

## M6.5 verifier standalone boot correction — candidate

The first operator direct-file invocation failed before querying telemetry because
Python started with `/app/scripts` on its import path and could not resolve
Django `config`. Module invocation is now the documented method; direct
execution explicitly includes the backend root on `sys.path`. A subprocess
regression covers startup with `PYTHONPATH` unset and a deliberately invalid
key, without relying on persisted data. The 223-backend/82-frontend release
gate passed before this correction; rerun it before committing. Live read-back
and manual operator acceptance remain pending.

## M6.5 read-back verification slice — implementation candidate

Baseline: committed/pushed `dc3b7bf2b2c22ad8a07dca7cb4f64c6482ca48bd`.
Operator previously reported 207 backend tests and 82 frontend tests passed.
This slice adds a key-derived tenant-scoped ClickHouse read-back verifier for
three correlated signals, an exact span-parent chain, and resource labels;
it has pure unit/negative/security-contract tests and an operator command.
**Not performed by this patch:** a real read-back run, different-user 404,
UI/keyboard/mobile proof, truncation/failure handling in the browser,
framework exporter, temporary-key revocation or current full Docker/hosted CI.
Leave M6.2–M6.5 closeout open until evidence is independently recorded.
Run focused tests and `scripts/verify.ps1`; record actual results and final SHA
before a clean commit/push. No new tables or ingestion API are introduced.


## M6.2–M6.4 operator evidence enabler — candidate 2026-10-24

Baseline GitHub `main` `f84f0bc8090d3dbf6827fa99370724a67d49ee86`.
Verified hosted GitHub Actions run for this baseline:
https://github.com/mooskyai/sentrix/actions/runs/40067501609 (`success`).
The operator-reported last Windows/Docker gate passed 194 backend and 74
frontend tests before this candidate. Add a standalone three-service OTLP/HTTP
smoke producer with correlation, infrastructure attributes, safe stdin key
handling and focused tests; update operator instructions and checklists without
marking them passed. No model, schema, API route, permission or UI change.
This candidate's Docker/full gate and actual manual acceptance are **not run**.
Review areas: README, PRD, DESIGN, ARCHITECTURE, DATABASE, API, AGENTS,
implementation, setup, feature development, auth/security, integrations,
QA, debugging and M6 plans. Only materially affected docs are changed.
M6.5 remains blocked on recorded M6.2–M6.4 acceptance.

## Workspace auto-default and stale localStorage preference — 2026-10-24 candidate

Starting from verified pushed `main` `41ed2104aa493aeb480803e0716fbedacfe4efe9`,
this client-only refinement selects the first authorized usable organization and
project when needed, remembers valid manual choices in versioned per-user
`localStorage`, marks replaced stale IDs explicitly, and migrates the former
session-scoped preference. Explicit valid URLs continue to win; unknown/foreign
URLs do not silently redirect to other projects. React component/pure helper
regression tests are included. This is a **patch candidate**: no local Docker
or hosted CI result, browser evidence, acceptance, commit or push is claimed.
Previous M6.4 code is pushed and local `scripts/verify.ps1` passed 194 backend
and 62 frontend tests; M6.2/M6.3/M6.4 manual acceptance remains unreported.
Document review: README, PRD, DESIGN, ARCHITECTURE, DATABASE, API, AGENTS,
ProjectImplementation, Setup, FeatureDevelopment, Authentication&Security,
Integrations, Testing&QA and Debugging. No server-side contracts, database,
telemetry, integration, ingestion or API route changes are introduced.

## M6.4 observed service map candidate — 2026-10-24

Baseline verified from GitHub `main`:
`8337cc14d17bc76413d5a6c9cd5418020163a737`. Candidate patch adds a
bounded tenant-first read-only service relationship query from stored parent and
child spans, `services/map/` endpoint, React relationship disclosure and tests.
Existing ClickHouse schema, ingestion, security roles and deployment are unchanged.
The candidate is **not verified on user Docker, not accepted, not committed or
pushed**. M6.2/M6.3 manual acceptance remains open; do not represent M6.4 as
shipped before real multi-service OTLP/browser proof and green release gate.
See `V1_M6_MILESTONE_TESTING.md` and `M6_4_BROWSER_ACCEPTANCE.md`.
Docs reviewed: README, PRD, DESIGN, ARCHITECTURE, DATABASE, API, AGENTS,
ProjectImplementation, Setup, FeatureDevelopment, Authentication&Security,
Integrations, Testing&QA and Debugging. Setup, Integrations and Debugging
contracts do not change with this read-only query.

## Repository terminology cleanup — 2026-10-24 (documentation only)

Baseline: `f0fc483803779911b3830e5beee7fc4b632f605e` (pushed `main`).
Replace named competitor references with Sentrix-first capability language in
ROADMAP, README, PRD, AGENTS, V1 M6 milestone and this register. No product
code, API, schema or feature scope changes. Existing M6.2/M6.3 acceptance
remains open. The operator reported a passing local release gate (182 backend,
58 frontend tests) for the previous CI correction, but its hosted Actions
rerun has not been independently verified here. This wording-only patch needs
application and review before commit/push; no new test pass is claimed.

## GitHub Actions ClickHouse/Redis dependency correction — 2026-10-24

**Baseline:** pushed `main` `001a3027d49e6847c6856e87e243a8d05e711967`.
The operator supplied a backend CI failure after 161 passing tests:
`test_all_otlp_signals_persist_to_clickhouse` errored during fixture setup with
`localhost:8123` connection refused. Inspection of `.github/workflows/ci.yml`
confirmed the backend job defined a PostgreSQL service but **no ClickHouse or
Redis service**, despite pointing `CLICKHOUSE_HOST` and `REDIS_URL` at localhost.
This patch adds health-checked ClickHouse 25.8 and Redis 8 job services and explicit
ClickHouse database/user/password/port settings. It does **not** alter test
assertions, ingestion code, database schema, or access policy. Candidate only:
actual GitHub Actions rerun and local `scripts/verify.ps1` remain unreported;
M6.2/M6.3 manual acceptance remains open. Do not call the CI failure fixed until
that rerun passes, and do not begin M6.4 based on this infrastructure correction.

## Roadmap alignment — 2026-10-24 (planning patch; not implementation)

Base GitHub `main`: `0939cca36f56c6106082976f8a5410ee022e9607`.
Documentation-only change: publish [ROADMAP.md](ROADMAP.md) and align product,
architecture, contributor workflow, integration, setup, design, test and V1 M6
plans around phased core observability outcomes. **No application
code, collector, schema or API was changed.** The roadmap artifact itself
is not a tested or committed milestone until the user applies and pushes it.

Correct the distinction in older snapshots: M6.3 infrastructure is pushed at
`75d2d21`; the sidebar/framework guides are pushed at `0939cca`. User-reported
prior release gate: **182 backend and 58 frontend passed**. Operator evidence
in `M6_2_BROWSER_ACCEPTANCE.md` and `M6_3_BROWSER_ACCEPTANCE.md` remains
unreported, so neither M6.2 nor M6.3 may be marked manually accepted. M6.4
and M6.5 remain future work. After this planning patch, verify Git diff,
review/check links, commit/push and record the resulting SHA in the next entry.

Documentation review: README, PRD, DESIGN, ARCHITECTURE, DATABASE, API,
AGENTS, ProjectImplementation, Setup, FeatureDevelopment,
Authentication&Security, Integrations, Testing&QA and Debugging; no new wire
formats, authorization model, schema or alert evaluator behavior is introduced,
so the existing API/database/debug contracts remain unchanged. M6 milestone,
testing and framework quickstart docs are synchronized here.

## Historical 2026-10-23 documentation patch preparation note

Repository baseline: `75d2d212259caf8bce579464e008ed8755c45493`, pushed GitHub main.
Adds a persistent authenticated Documentation sidebar entry and Laravel, Node.js, React/Vite,
Next.js server-side onboarding. API reference route is unchanged but navigation links are hidden.
Keeps existing Settings key creation and docs entry; does not expose a secret to browser code.
The earlier M6.3 plus docs patch passed 182 backend/57 frontend tests and full release gate,
and was pushed at this baseline. The **new** sidebar patch needs user-run verification and
browser acceptance before commit/push or any M6.4 progression. M6.2/M6.3 manual acceptance
remains unreported; do not mark accepted from this doc change.
Reviewed README, Setup, DESIGN, Testing&QA, FeatureDevelopment, Authentication&Security, API,
Integrations, and milestone scopes; no telemetry endpoint/schema/auth contract is modified.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 candidate baseline: `78e1a94a02a5f258678f17bb1362650a82c7aff5` (clean pushed GitHub main
verified 2026-10-23). Planned patch adds read-only infrastructure query + DRF route,
Infrastructure workspace, backend security/OTLP integration tests, frontend tests and
`M6_3_BROWSER_ACCEPTANCE.md`. **Status: code patch prepared; no Docker checks/browser operational
proof or resulting commit/push claimed.** User explicitly requested M6.3 implementation while M6.2
manual browser acceptance was still outstanding; this does not retroactively accept M6.2. Document
review: PRD, DESIGN, ARCHITECTURE, DATABASE, API, AGENTS, README, ProjectImplementation, Setup,
FeatureDevelopment, Authentication&Security, Integrations, Testing&QA, Debugging reviewed and
updated where operational status/contract is affected. M6.4 stays blocked.

## Pre-M6.3 UI refinement — pushed; final acceptance pending

The compact header selectors, authorized project navigation and detail drawers are
implemented and visually approved. The final single-level card correction was committed
and pushed at `a4bcb4c`. The post-correction `scripts/verify.ps1` gate passed
on 2026-10-22 (170 backend, 50 frontend tests). Manual M6.2 browser
acceptance remains unreported. M6.3 stays blocked until it is recorded and
the closeout documentation is committed and pushed.
See `UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

## Final UI automated verification — 2026-10-22

Tested UI commit: `a4bcb4c4274fde5b5199a973f46060c375c4286b`.
The operator reported 29 focused service catalog/detail tests passing (one
warning); the full `scripts/verify.ps1` gate passed with 170 backend tests
(one warning) and 50 frontend tests across 11 files. Ruff check/format,
mypy on 101 files, Django checks and migration drift, ClickHouse schema,
ESLint, TypeScript, Vite build and Git whitespace checks all passed.
The documentation-only follow-up was pushed as `fb36906230c31ff6b7eccba03ec45c8bbe384379`,
and GitHub `main` was confirmed there on 2026-10-23.

Manual Services/browser/foreign-user acceptance has not been reported.
The two synthetic demo organizations accessible to the same user do not
prove foreign-user non-discovery. M6.3 is blocked until the actual browser
acceptance record is completed, committed and pushed.

Documentation review for this evidence-only correction: README,
ProjectImplementation, Testing&QA, M6_2_BROWSER_ACCEPTANCE,
UI_DENSITY_AND_DRAWERS, both V1_M6 milestone documents, PRD, DESIGN,
ARCHITECTURE, AGENTS and FeatureDevelopment updated; DATABASE, API,
Setup, Authentication&Security, Integrations and Debugging reviewed with
no material contract, schema or configuration change.

## Historical M6.2/seeder checkpoint — 2026-10-21

This older verification record predates final UI correction `a4bcb4c`.
Its 44 frontend tests are historical; the later 50-test UI release gate
is documented above. M6.2 manual browser acceptance remains open.

**Canonical repository:** `https://github.com/mooskyai/sentrix`
**Last independently confirmed pushed SHA:** `4b34f3c926b75ce997a2e07f8c15520556624ba8`
(`feat(dev): add V1 M1-M6.2 demo data seeder`), clean `main...origin/main` on the acceptance host.
**M6.2 code commit:** `a0e78817749e6a235194cb71d5a9349e4e9844b9`
(`feat(services): complete M6.2 service workspace and detail`).
**Automated verification:** `scripts/verify.ps1` passed on Windows/Docker after seeding:
170 backend tests (including six seeder tests), 44 frontend tests, Ruff lint/format,
mypy (101 Python source files), Django system/migration checks, ClickHouse schema,
TypeScript, ESLint, Vite production build and Git whitespace check. One pytest warning
was reported, with no test failures.
**Runtime fixture:** `manage.py seed_demo --username admin` completed successfully,
creating/reusing two demo organizations with real OTLP-persisted synthetic observations.
This is development fixture data, not external exporter evidence or production telemetry.
**Remaining M6.2 acceptance:** manual browser checks for the Services detail view,
project switching, trace navigation and UI states have **not yet been reported**.
See `M6_2_BROWSER_ACCEPTANCE.md`. Do not start M6.3 until this evidence and
its documentation closeout are recorded and pushed.

## 1. Milestone implementation status

| Milestone | Outcome | State | Evidence |
| --- | --- | --- | --- |
| V1 M1 | Django/React control plane, auth, org/project tenancy, roles, health, visual foundation | Implemented | `V1_MILESTONE.md`, `V1_MILESTONE_TESTING.md` |
| V1 M2 | project API keys, OTLP/HTTP protocol + durable ClickHouse storage; real trace smoke | Implemented | `V1_M2_MILESTONE*.md`, `scripts/verify-m2.ps1` |
| V1 M3 | bounded scalar metrics queries, Metrics explorer, dashboard panels, real metric smoke | Implemented | `V1_M3_MILESTONE*.md`, `scripts/verify-m3.ps1` |
| V1 M4 | bounded log search, Logs explorer, exact trace lookup/navigation, operational smoke | Implemented | `V1_M4_MILESTONE*.md`, `scripts/verify-m4.ps1` |
| V1 M5 | metric rules/current evaluation state, Alerts workspace, signed webhook channels/delivery, real OTLP + browser smoke | **Complete / pushed** | `V1_M5_MILESTONE*.md`, `scripts/verify-m5.ps1`; `d43947a` |
| V1 M6 | service catalog, detail, host/K8s resource discovery, observed service relationships, operational closeout | **M6.1 accepted; M6.2 code pushed, browser acceptance open** | `2c1b5a2`, `a0e7881`, `4b34f3c`, `V1_M6_MILESTONE*.md` |

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

Run and record `M6_2_BROWSER_ACCEPTANCE.md` in the seeded demo organizations (plus
independent external-OTLP evidence if claiming an operational production-like smoke).
All M6.2 code, seeder, 170-backend/44-frontend full gate and clean push are already verified.
After browser results are recorded and documentation updated/pushed, M6.3 may start from
that **new** clean GitHub commit, not from `2c1b5a2`.

## 6. V1 M6 detailed implementation ledger — live

The M6 plan is delivered one accepted slice at a time. M6.2 implementation is pushed and
automated verification is green; its manual browser gate remains open. M6.3–M6.5 are planned.

| Slice | Deliverable | Current status | Remaining acceptance requirement |
| --- | --- | --- | --- |
| M6.1 | Authorization-first, bounded multi-signal service catalog API | **Completed/pushed** `2c1b5a2` | None; historical 15 focused / 150 backend / 35 frontend gate |
| M6.2 | Services list/detail browser and correlation links | **Code pushed** `a0e7881`; demo seeder `4b34f3c`; **browser pending** | Project switch, trace-ID link, empty/error/truncation UI proof; update docs |
| M6.3 | Host/Kubernetes attribute-based resource views | **Planned / blocked** | Exact attribute evidence and partial/missing-attribute behavior |
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

## V1 M6.2 — Services workspace (implementation pushed; browser gate pending)

Baseline `2c1b5a2c18d1929b37ff0a55796eaceb41070592`.
Implementation pushed at `a0e78817749e6a235194cb71d5a9349e4e9844b9`.
The authenticated Services workspace reads the M6.1 multi-signal catalog and separately
queries `/api/v1/projects/{project_id}/services/detail/` for **exact** service name,
environment (including empty), and bounded UTC window. Detail returns up to 50 metric names,
20 recent error logs and 50 observed trace references, each with explicit truncation.
The UI links observed trace IDs to the existing Traces explorer with project/window context.
Generic Metrics and Logs links preserve the project but do not silently prefilter.
Neither route invents health, ownership, SLOs, uptime or inventory.

The demo fixture command, tests and documentation were pushed at `4b34f3c`.
A subsequent full gate passed: 170 backend tests, 44 frontend tests, Ruff, mypy,
Django/ClickHouse checks and production build. API tests exercise foreign project 404
before ClickHouse and exact empty-environment queries; integration tests persist OTLP
signals to real ClickHouse. No new schema, model, migration or worker is introduced.

**Open:** complete and document the manual Services browser walkthrough in
`M6_2_BROWSER_ACCEPTANCE.md`, including project switching and correlation links.
The two seeded organizations are accessible to the same user and are *not* proof of
foreign-user authorization. Do not mark M6.2 fully accepted or begin M6.3 beforehand.

### Pre-M6.3 UI refinement — flat workspace surfaces

The shared project-section container no longer carries panel chrome. Service
detail inside the right-hand drawer likewise avoids an extra bordered card;
Overview facts and genuinely independent alerts/data groups remain separated.
This UI-only change follows the global-header/drawers patches and adds a page
layout regression test. It requires frontend gates, full release gate, manual
browser acceptance, commit and push before starting M6.3.

The subsequent data-first presentation attempt removed too many visible cards
and was superseded by the final single-level card correction at `a4bcb4c`.
All those changes are pushed and the final full gate has passed; manual
browser acceptance remains unreported. M6.3 remains on hold.

The follow-up card-hierarchy correction restores one content surface for
Services/Metrics/Logs/Traces/Settings while leaving Overview/Dashboards/Alerts
item cards as siblings. Toolbars, plots and tables inside a content card do
not get another border. This UI-only correction is pushed at `a4bcb4c`. Post-correction
release-gate output passed on 2026-10-22; manual browser acceptance is still
required before M6.3.

## Linked project documentation — implementation candidate

Baseline: `78e1a94a02a5f258678f17bb1362650a82c7aff5` (verified remote `main`). This UI-only documentation change adds Settings links to authenticated `/docs/telemetry-setup` and `/docs/api-reference` pages, along with Python OTLP setup, machine-versus-session authentication, API endpoint details and frontend tests. No project API-key authorization boundary or telemetry behavior changes. Both owner/writer and viewer states expose the links without exposing credentials.

Validation pending on Windows/Docker: focused `ProjectApiKeysPanel.test.tsx` and `DocumentationPages.test.tsx`, frontend lint/type/build, complete `scripts/verify.ps1`, and browser navigation from project Settings. Do not mark these gates passed, or M6.2/M6.3 browser acceptance complete, without observed results. This patch is deliberately independent of the M6.3 infrastructure candidate (which has not been verified/committed in the provided handoff); recheck the actual local SHA and patch compatibility before applying either.

Documentation reviewed: README, API, DESIGN, ProjectImplementation, Testing&QA, Setup, Authentication&Security, FeatureDevelopment; architecture, DB, integrations, PRD, agent and active milestone docs have no new technical contract from documentation links.
