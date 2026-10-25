# Sentrix — repository contributor and agent instructions

## M7.1 candidate guardrails

The first-telemetry endpoint is a read-only, session-authenticated observation
summary, not a project-key validation API, connection health signal, active
network probe or runtime integration certificate. Resolve project membership
before ClickHouse. Use server-derived tenant predicates, fixed 24-hour bounds
and read budgets; return sanitized 503 for query failure. Never send, store,
log or copy an ingestion secret to the frontend. Do not mark M6 accepted or
M7.1 live-certified solely because automated tests pass.

## Master milestone acceptance index — documentation-only coordination

`MILESTONE_ACCEPTANCE_CHECKLIST.md` is the cross-milestone M1–M12 proof index.
It does **not** supersede existing per-milestone test matrices, imply planned
M7–M12 capabilities are implemented, or close the open M6.2–M6.5 manual
operator gates. Link acceptance entries to real, nonsecret evidence, tested
SHA, CI result, independent-user authorization, teardown and reviewer sign-off.
Documentation-only checklist additions still require a clean diff, quality
checks, synchronized implementation register and a commit/push before release.

## M6.5 read-back candidate — pending operator sign-off

Baseline `dc3b7bf` starts a read-only persisted-evidence verifier; it must
never accept organization/project UUIDs from the operator or telemetry data.
Require temporary key only from stdin; avoid printing tokens or raw payloads.
Do not label an HTTP 200, unit test or even successful DB read-back as M6
acceptance. Separate-user 404, operator browser evidence, external SDK signal,
controlled failure/retry, cleanup, release gate and CI remain explicit gates.


## M6 closeout evidence — candidate at `f84f0bc`

`backend/scripts/m6_acceptance_smoke.py` provides a controlled, independent-process
OTLP/HTTP protobuf producer with three services/signals; see
`docs/M6_ACCEPTANCE_PRODUCER.md`. It does not establish actual Kubernetes
inventory, external framework certification, foreign-user isolation, UI
acceptance, or a successful ClickHouse read. Never silently mark M6.2–M6.4
checklist items accepted from its stdout or a passing pytest suite. Operator
proof, revocation of the temporary key, and clean committed records precede M6.5.

## Per-user workspace selection persistence contract — candidate

The UI may store only organization/project identifiers, a schema version, and a
stale-selection flag in per-user `localStorage`. Always revalidate against the
authenticated API membership/project lists; storage, a deep link or a displayed
selector is never an access grant. Default to the first authorized usable pair
if there is no valid choice. Mark replaced/removed stored choices stale; clear
that flag on a user selection or a valid authorized deep link. On invalid explicit
workspace URLs, retain the not-found result and do not silently substitute a
neighboring tenant. Never store access tokens, telemetry or secrets in this record.

## M6.4 implementation candidate — acceptance remains blocked

The observed service map code must not be represented as accepted until the
separate M6.2/M6.3 manual evidence is recorded and the M6.4 tests, real external
OTLP multi-service evidence, browser checks, full release gate and clean commit
are reported. Preserve strict server-side tenancy and require stored same-trace
span parentage; do not infer graph edges or service health. Keep the roadmap
independent of competitor names and do not rewrite historical acceptance facts.

## GitHub Actions real-dependency invariant — 2026-10-24

CI executes pytest on the Ubuntu host, not the Compose `api` container. Keep
PostgreSQL, Redis and ClickHouse health-checked CI services aligned with their
host-side `localhost` environment variables; Compose uses service DNS names.
Do not disable live ClickHouse integration tests to mask missing infrastructure.
A passing local Docker release gate does not certify GitHub Actions.

## Standing roadmap execution contract — current 2026-10-24

Treat [ROADMAP.md](ROADMAP.md) as the ordered **planning** source, not proof of
runtime functionality. Canonical implementation truth remains committed code,
operator results and acceptance checklists. At `0939cca`, M6.3 infrastructure
and framework documentation are pushed; M6.2/M6.3 manual acceptance stays open.
Never begin M6.4 until both acceptance checklists are completed and pushed.

For each new Sentrix workflow, prefer OpenTelemetry SDKs/Collector,
but verify *actual framework processes*, data reception and supported signals.
Do not claim a proprietary agent, gRPC/JSON ingestion, an all-in-one collector,
Kubernetes inventory, automatic alert scheduling, RUM or a new Sentrix SDK.
Keep browser credentials public-safe and ingestion keys server-only. First
specify auth, tenancy, cardinality, retention, query limits and failure modes;
then deliver one patch, focused/full verification, real acceptance, docs,
commit/push and a clean aligned `main`.

Keep repository documentation, UI text, tests and release notes Sentrix-first.
Avoid named competitor references unless the product owner changes this policy;
describe concrete supported capabilities and evidence instead of comparisons.

## Historical M6.3 candidate instruction (superseded by current status)

M6.3 candidate implementation from verified pushed baseline
`78e1a94a02a5f258678f17bb1362650a82c7aff5` remains unverified until focused/full Docker gates,
real OTLP, browser acceptance, documentation closeout, commit and push. Continue following the
14-document review rule. Preserve approved card hierarchy/global selectors/drawers, tenant-first
queries, no fabricated inventory, and no M6.4 before M6.3 acceptance.

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

> **Scope:** Entire repository. Treat this file as the standing contract for humans and coding agents. V1 M1–M5 and M6.1 are accepted. M6.2 code and demo fixtures are pushed; automated gates passed, but manual browser acceptance is unreported. M6.3–M6.5 remain planned. Inspect the latest Git state before treating a slice as complete.

## Repository authority and workflow

1. Canonical repository: `https://github.com/mooskyai/sentrix`. Primary acceptance checkout: `C:\working\Projects\Python\sentrix` on Windows 11 / PowerShell 7.
2. Before touching code or writing a patch, run `git status -sb`, `git rev-parse HEAD`, and inspect the actual files. Patches must apply against the exact reported baseline, not a remembered commit.
3. Work one bounded, reviewed slice at a time. Never force-apply, guess conflict resolutions, or use `git apply --3way` to hide baseline drift. Provide an apply-ready patch including **new files**.
4. Code, tests, migrations/schema changes, docs, and operational acceptance must align. Do not suggest a commit if the automated checks or required real-runtime acceptance failed.
5. Once green, one clean commit per accepted slice, push, then verify `## main...origin/main`. Do not claim a push from generated code or a patch alone.

## Architecture invariants

- Django + PostgreSQL own users, organizations, memberships, projects, credentials, dashboard configuration, alert rules/states/channels, and delivery retry state.
- ClickHouse owns raw OpenTelemetry metrics, logs, and spans. Never duplicate raw samples/history into PostgreSQL.
- Redis is ephemeral coordination; existing Redis does **not** authorize a new queue/scheduler framework.
- Browser uses cookie session + CSRF, not a machine API key. OTLP/HTTP uses a scoped project Bearer key, not a browser session.
- Resolve the authorized project via membership **before** opening any data-plane client. Derive `(organization_id, project_id)` from trusted server-side relationships; never from slugs, URLs, query strings, OTel resource attributes, or caller-supplied IDs.
- Unknown and foreign project resources are non-discoverable. Owner/admin/editor can perform documented write actions; viewers have read-only access where supported.
- Keep time windows/limits bounded and telemetry query parameters typed. Preserve raw signal semantics: no fabricated values, service health, dependencies, or aggregate/rate semantics.
- External webhook transport stays outside request handlers and evaluator transactions. Keep signing credentials and endpoints out of ordinary read payloads and logs.

## Mandatory documentation synchronization — every development slice

Before considering a change complete, **review all 14 requested documentation roles** (12 new files plus existing `README.md` and `ARCHITECTURE.md`). Update every affected page in the **same patch** as code; do not insert meaningless touch-only edits into unrelated docs. At minimum, update `README.md` for user-visible behavior/setup and `ProjectImplementation.md` for milestone progress, verification evidence, and next steps. Update the relevant `V1_M*_MILESTONE.md` and `V1_M*_MILESTONE_TESTING.md` for active work. Even documentation-only planning changes must update the implementation register.

| Documentation | Required when changing |
| --- | --- |
| `PRD.md` | product goals, supported workflows, scope, acceptance, roadmap |
| `DESIGN.md` | navigation, UI states, design system, component contracts |
| `ARCHITECTURE.md` | boundaries, flows, integration patterns, deployment |
| `DATABASE.md` | models, fields, indexes, migrations, ClickHouse schema |
| `API.md` | routes, auth, request/response shapes, error semantics |
| `AGENTS.md` | workflow, coding-agent requirements, standing constraints |
| `README.md` | discoverability, setup, features, major milestones, doc links |
| `ProjectImplementation.md` | **every completed slice**: SHA, status, change summary, tests, operational proof |
| `Setup.md` | env, Docker, bootstrap, configuration, local workflow |
| `FeatureDevelopment.md` | slice process, implementation patterns, new features |
| `Authentication&Security.md` | roles, credentials, egress, tenant privacy, threat model |
| `Integrations.md` | OTLP, webhook, external integration contracts |
| `Testing&QA.md` | test cases, quality gates, smoke acceptance, CI |
| `Debugging.md` | failure signatures, reproducible diagnosis, recovery commands |

Required completion checklist: [ ] code/build/tests [ ] tenant/security review [ ] database/API review [ ] user/operations impact [ ] all docs reviewed [ ] affected docs updated [ ] changelog/implementation entry [ ] no secret/generated files [ ] clean patch [ ] human acceptance where specified [ ] commit/push/clean branch.

## Development and verification

```powershell
git status -sb
git rev-parse HEAD
docker compose config --quiet
.\scripts\verify.ps1
```

Run targeted backend/frontend tests first, then full verifier. The operational verifiers are `verify-m2.ps1` (traces), `verify-m3.ps1` (metrics/dashboard), `verify-m4.ps1` (logs/traces), and `verify-m5.ps1` (alert webhooks). M5 verifies an isolated temporary project and cleans up control-plane fixtures, but leaves unique ClickHouse smoke telemetry as ordinary data. Never run `docker compose down -v` as part of verification or troubleshooting.

API container commands use `/opt/venv/bin/python`, `/opt/venv/bin/ruff`, `/opt/venv/bin/mypy`; frontend checks run under `/app`. The release gate must include backend pytest/Ruff/mypy/Django/migration/schema plus frontend lint/typecheck/tests/build. Changes to schema need migrations or explicit ClickHouse schema commands and matching tests.

## Security and response hygiene

No raw keys, passwords, signing secrets, session cookies, full sensitive webhook URLs, receiver bodies, or unrestricted telemetry payloads in commits, diagnostics, example outputs, or chat transcripts. Never log arbitrary exception strings from external delivery. Label absent data accurately; treat dependency failures distinctly from healthy empty results. If tooling cannot reproduce a state, record the blocker rather than declaring success.

## Documentation conventions

- Files use the exact repository names in the table. **Do not add `Readme.md`** on Windows: `README.md` already fulfils that role.
- Keep facts labeled **Implemented**, **Planned**, or **Out of scope**. Do not present M6 or optional future infrastructure as shipping V1 capability.
- Link to code and existing `V1_M*_MILESTONE*.md` details instead of copying potentially stale test counts or inferred schemas. `ARCHITECTURE.md` remains the detailed technical architecture source; `DESIGN.md` is UI/UX design, not a replacement.
- Treat docs as versioned source artifacts; amend them in the code patch, never solely in an ephemeral summary.

## Required V1 M1–M6 documentation lifecycle

All milestone work must keep historical truth and future intent separate. At the M5 closeout baseline `d43947a`, **M1–M5 are delivered** and **M6.1–M6.5 are planned only**. The M6 planning documents `V1_M6_MILESTONE.md` and `V1_M6_MILESTONE_TESTING.md` must be present before M6 implementation. Their existence is not proof M6 code shipped.

For **every** subsequent code/docs slice, inspect *all fourteen* handbook areas listed above and update each materially affected one **in the same apply-ready patch**. Also update active milestone and testing docs; record the exact observed baseline, implementation state, tests, real operational/browser evidence, resulting SHA and remote sync in `ProjectImplementation.md`. If a document has no material change, record that it was reviewed in the change summary, rather than adding meaningless lines. At a minimum, the project README, implementation register, current milestone tests, and at least the directly impacted API/database/security/design reference must be evaluated.

When releasing M6 changes: enforce query-time tenant-first ClickHouse scoping, real-signal evidence, no inferred service health or topology, no unsanctioned persistence, and strong positive/negative tests. Do not begin M6.2 before M6.1 has a green gate, documentation sync, commit/push and clean `main`. Continue the same rule through M6.5. Re-review these agent instructions whenever a milestone changes the architecture or operational workflow.
