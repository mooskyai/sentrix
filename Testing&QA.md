# Sentrix — Testing and Quality Assurance

## M7.3.3a Next.js — local functional/security acceptance COMPLETE; release CI PENDING (2026-10-27)

Real Next.js App Router `GET /api/checkout` exported a manually instrumented
OTLP `SERVER` span to the authenticated project's ClickHouse store. Independent
read-back verified trace `406fa3db23e9f4c8c98e975424a6179d`, run
`49a30251d0c749ceb75cd56b9e6406ce` at `2026-10-27T06:17:16.097Z`, service
`m7-nextjs-node-runtime`, environment `integration`. Owner trace/Services API
reads returned HTTP 200; foreign-user requests returned HTTP 404. The operator
confirmed all three browser checks and attested the *same* temporary export
credential was subsequently revoked and rejected by live OTLP HTTP 401.
Local verification: **308 backend**, **103 frontend**, **18 focused Next.js
backend** and **4 Next.js real-process** tests passed; npm audit reported zero
vulnerabilities. **Lockfile and staged-change review, final commit/push and
exact-SHA GitHub Actions CI remain OPEN.** See
`docs/M7_3_3A_LOCAL_EVIDENCE_2026_10_27.md`. The broader M7.3 runtime matrix,
M7.4 and production readiness are not accepted by this isolated slice.

## M7.3.2 latest operator acceptance / release gate (2026-10-27)

Direct Node/Express SDK ClickHouse read-back succeeded in current project
`2017c79d-981f-4f92-9833-303729a4605e`. Authenticated owner read 200 and
foreign nonmember received 404 for the exact trace and Services API; browser
access, nonmember isolation and deep-link denial were operator-confirmed.
Database showed the exposed temporary key revoked and live OTLP returned 401.
`./scripts/verify.ps1` passed **290 backend** (1 warning), **103 frontend**,
Ruff, mypy (130 files), Django, ClickHouse and Vite build. See the sanitized
[final evidence](docs/M7_3_2_FINAL_ACCEPTANCE_2026_10_27.md). Commit/push and
exact-SHA CI remain open; 2026-10-26 metrics below are historical.

## Year-history fixture quality gate

`backend/apps/telemetry/tests/test_seed_demo_year.py` covers deterministic
correlation, explicit fake Node identity, day bounds, no-membership safety,
per-signal resumability, and a live two-day ClickHouse/authorization smoke.
Run targeted pytest and the full `scripts/verify.ps1`. A one-year seed is not
a substitute for actual Node SDK read-back, browser, HTTP 404, HTTP 401 or CI.
See `docs/DEMO_YEAR_SEED.md`.

## M7.3.2 — real SDK persistence and post-rebuild test evidence (2026-10-26)

Operator confirmed direct (non-relayed) Node SDK chunked export followed by
project-scoped ClickHouse read-back of exactly one Express SERVER span, run
`ddbaab4290524f2092254fb23ff01613`, trace
`2f06c0b95492feea6379d231993c5b5d`. After rebuilding with Uvicorn ASGI,
`./scripts/verify.ps1` passed **277 backend / 103 frontend**, Ruff, mypy,
Django/ClickHouse schema checks and frontend build. Independent fixture tests
passed **4/4** with npm audit **0 vulnerabilities**. Negative foreign-user
HTTP 404 and revoked-key HTTP 401, browser, post-commit CI and teardown are
still OPEN. The new `test_m7_node_auth_smoke.py` checks only the validation
helper and empty-body revoked-key probe without real credentials; the operator
must run both acceptance commands against live services and an actual foreign user
and record their real outcomes. See `docs/M7_NODE_CLOSEOUT_EVIDENCE.md`.

## M7.3.2 — HTTP framing correction gate (candidate)

The local API now uses installed Uvicorn ASGI instead of Django's WSGI
development server. Add regression checks that an unreadable chunked OTLP
body produces 400 rather than a false 200 and that populated trace requests
with a chunked header still reach the tenant-bound sink. This is unit
coverage, **not** proof that Uvicorn received an actual streamed HTTP body.
Run Ruff, format, mypy, focused `test_otlp_http.py`, 4 Node SDK tests and full
`scripts/verify.ps1`. Inspect the Node fixture's actual framing using
`node integrations/m7-node-express/inspect-framing.cjs`; restart only the
Compose API service and repeat `probe.cjs` with strict independent read-back.
See `docs/M7_NODE_HTTP_FRAMING.md`. Acceptance remains OPEN.

## M7.3.2 — canonical Node SDK wire inspection (candidate)

`python -m pytest apps/telemetry/tests/test_m7_node_wire_inspect.py -v`
checks that a complete OTLP trace normalizes to one row and malformed, hollow
resource and wrong-ID payloads fail closed. The live relay in
`integrations/m7-node-express/diagnose.cjs` forwards the same SDK protobuf
bytes to Sentrix, performs offline Django decoding, then an independent
authenticated ClickHouse read-back. No live success is claimed.
See `docs/M7_NODE_WIRE_DIAGNOSIS.md`.

## M7 synthetic Node UI seeder — separate from real exporter tests

`test_seed_demo.py` checks one synthetic `demo-node-express` SERVER root span
in the primary demo fixture with exact HTTP route, resource labels and distinct
trace ID; secondary project remains isolated. The existing live seeder test
checks the real project-scoped OTLP ingestion and Services catalog, but that
is still synthetic producer input. Run Ruff/format/mypy first, focused seeder
tests and `scripts/verify.ps1`; separately require real Node SDK ClickHouse
read-back to pass before M7.3.2 sign-off.

## M7.3.2 — Node exporter and persistence evidence (pending live tests)

Run `npm test` in the isolated fixture after reviewing/generating its npm
lockfile; the test subprocess sends real OTLP protobuf to a fake local receiver.
Run focused `test_m7_node_runtime.py`, Ruff/format/mypy preflight, then
`scripts/verify.ps1`, a live Express exporter, and authenticated persisted
read-back. No fake receiver or HTTP 200 establishes durable storage.
Record CI and foreign-user/browser/credential-teardown evidence separately.

## M7.3.1 observed operator gate and persisted Django trace (2026-10-25)

The corrected release gate passed 250 backend tests and 102 frontend tests,
including Ruff and strict mypy preflight, Django/schema checks and frontend
build. The isolated Django OpenTelemetry HTTP export and exact project-scoped
ClickHouse read-back succeeded for run `3ac7ac6765ea487cbd5de61b32bb1090`
and trace `06b5945cf479625c5a7a051bb748ca3a` (UTC producer time
`2026-10-25T08:18:57.946820+00:00`). This establishes a real stored Django
server span, not auto-instrumentation coverage or M7 operational acceptance.
Manual browser, independent-user, credential cleanup, other framework and
pushed-SHA CI gates are still open. See `V1_M7_MILESTONE_TESTING.md`.

## Mandatory Ruff and mypy preflight — M7.3.1 correction

`scripts/verify.ps1` validates Compose, then executes `ruff check .`,
`ruff format --check .` and strict `mypy .` before `python -m pytest`.
The M7.3.1 correction resolves the dynamic Django URL declaration and two
ClickHouse read-back `Any` return paths. Re-run the complete release gate and
independent real OTLP/ClickHouse read-back; previously passing unit tests do
not by themselves establish runtime or browser acceptance.

## M7.3.1 UTC ClickHouse read-back regression — candidate

Run the Ruff and strict mypy preflight before pytest. The read-back tests must
accept naive UTC `DateTime64` datetimes returned by ClickHouse Connect while
rejecting naive/aware timestamps outside the exact run window and non-datetime
values. This does not weaken project-key-derived tenant, service, environment,
run marker or trace-ID checks. Re-run the same operator-produced trace's
persistence verifier before recording verified storage; M7.3.1 acceptance
remains open until proof and cleanup are recorded.

## M7.3.1 Django runtime test plan — not yet operator accepted

Run `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_m7_django_runtime.py -v`, then `./scripts/verify.ps1`.
The tests launch a real isolated Django WSGI process and a local fake OTLP
HTTP receiver, asserting genuine upstream SDK protobuf transport; they also
validate ClickHouse tenant predicates, timestamp/result caps and negative rows.
A fake receiver does not demonstrate Sentrix storage. Separately run the
masked-key SDK producer and persisted read-back described at
`docs/M7_DJANGO_RUNTIME_ACCEPTANCE.md`; record browser/foreign-user/cleanup
results as **NOT RUN** until explicitly executed. Do not close M6 gates.

## M7.2 guided server integration regression matrix — candidate

New `frontend/src/guidedIntegration.test.ts` tests endpoint selection,
injection-resistant snippet identifiers and project/service/environment
matching (including truncated results). `GuidedIntegrationPanel.test.tsx`
tests no implicit requests, bounded explicit project query, exact match,
truncation/no-data/503, HTTPS-only remote, framework changes and secret-free
copies. Run focused Vitest, then `scripts/verify.ps1`; live Django/Node server
instrumentation and browser/keyboard acceptance remain unverified until
operator evidence is recorded in `V1_M7_MILESTONE_TESTING.md`.

## M7.1 first-telemetry diagnostics gate — candidate

Run `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_connection_diagnostics_api.py -v`, and
`docker compose exec -T web npm run test -- --run
src/components/ConnectionDiagnosticsPanel.test.tsx` (or the repository's
Vitest command). Then run `./scripts/verify.ps1`. Backend tests assert
membership before ClickHouse, typed tenant predicates, fixed 24h bounds,
real signal counts, safe empty/503 behavior and client closure. Frontend tests
cover observed, missing, failed and manual refresh states without credential
exposure. Operator must also test another user and separate real exporter.
No M6 acceptance record is closed by this candidate.

## Master milestone proof and operator status

The [M1–M12 acceptance checklist](MILESTONE_ACCEPTANCE_CHECKLIST.md) links
V1 M1–M6 detailed test plans, records the outstanding M6.2–M6.5 manual gates,
and lists **provisional** future M7–M12 acceptance criteria. Preserve the
original case IDs and real operator records; checkboxes alone are not proof.
For every acceptance run record SHA, scoped result, CI, independent-user 404,
live signal/host evidence, UI/failure/limit checks, credential cleanup and
release sign-off. A full automated gate does not substitute for manual checks.

## M6.5 standalone CLI import-path regression

`test_m6_readback_cli.py` runs the read-back entry point as a direct script
with `PYTHONPATH` removed and a deliberately malformed project key. It must
initialize Django and reject the key without `ModuleNotFoundError`; this is
only a startup check, not a database read-back or credential authorization
proof. Prefer `python -m scripts.m6_readback` for operator invocations.

## M6.5 persisted read-back candidate (not manual acceptance)

Focused verifier checks:
`docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_m6_readback.py -v`.
The verifier uses only an authenticated temporary project's scope and executes
bounded typed ClickHouse queries; tests reject fabricated/missing persistence,
incorrect trace/log correlation and false parent links. Actual operator
read-back plus independent foreign-user 404 and browser/UI evidence remain
outstanding, even when the full `scripts/verify.ps1` gate is green.


## M6 operator OTLP producer — candidate validation

Focused test: `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_m6_acceptance_smoke.py -v`. It asserts three real
protobuf signal shapes, strict same-trace parent/child IDs, co-observed
resource attributes, sanitized failure handling and safe HTTP origins.
Run full `scripts/verify.ps1` afterwards. `docs/M6_ACCEPTANCE_PRODUCER.md`
requires actual browser read-back and a separate real application/Collector
producer before claiming external instrumentation. Hosted CI for baseline
`f84f0bc` passed; this candidate patch is not yet verified there.

## Auto-selection/localStorage regression gate — candidate

Run `docker compose exec -T web npm test -- --run src/components/AppShell.test.tsx
src/workspacePersistence.test.ts` and full `scripts/verify.ps1`. Cover first usable
organization/project on clean storage, persistence of a valid manual choice,
organization switch selecting its first project, legacy sessionStorage migration,
project/org deletion or mismatch marking the versioned localStorage record stale,
no-data and disabled-storage behavior, a separately signed-in user, browser
navigation/deep links and unauthorized URLs. Repeat with real browser refresh,
account sign-out/in and two organizations. No browser acceptance is presumed.

## M6.4 observed map verification (candidate)

Focused backend: `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_service_map_api.py -v` (including live ClickHouse).
Focused UI: `docker compose exec -T web npm test -- --run
src/components/ServiceMapPanel.test.tsx src/components/ServicesWorkspace.test.tsx`.
Then `./scripts/verify.ps1`, real OTLP producer and separate authenticated
browser/foreign-user tests in `M6_4_BROWSER_ACCEPTANCE.md`. Ensure neither
expired trace IDs nor incomplete scans lead to fabricated topology.

## GitHub Actions live-dependency integration tests — 2026-10-24

CI runs `uv run pytest -q` from the Ubuntu runner and includes integration tests
for real OTLP/HTTP persistence in ClickHouse. Therefore the backend GitHub Actions
job must start healthy PostgreSQL (`localhost:5432`), Redis (`localhost:6379`),
and ClickHouse (`localhost:8123`, database `sentrix`) service containers.
The runner resolves `localhost`; the Docker Compose API container resolves
`postgres`, `redis`, and `clickhouse` by service name. Never replace real
persistence tests with mocks or skip `@pytest.mark.integration` merely to turn
CI green. Validate that the job proceeds beyond
`test_all_otlp_signals_persist_to_clickhouse`, completes all tests, and
passes the full workflow. Record the run URL and commit SHA in the closeout.
A connection-refused setup error indicates a missing/unhealthy network service,
not a failed telemetry-persistence assertion.

## Roadmap-wide acceptance matrix (2026-10-24)

See [ROADMAP.md](ROADMAP.md) for scoped future milestone targets, never as
proof of shipped features. Existing baseline `0939cca` had a user-reported
182-backend/58-frontend release gate. M6.2/M6.3 manual browser evidence
remains open (two independent acceptance files). This docs change does not
rerun automated tests or verify real framework instrumentation.

Future integration tests must include a real exported OTLP trace for each
advertised server framework, correct project/service/time correlation,
invalid/expired/foreign keys, connectivity and ClickHouse 503, duplicate/
retry/flush outcomes and no credential in browser bundles. Later APM/infrastructure
and alert-worker milestones add statistical correctness, cardinality/cost,
resource/tenant isolation, failover and transport durability tests respectively.
Every claimed user-visible feature needs browser/mobile/keyboard evidence.

## Historical onboarding verification checklist (automation passed; manual open)

Verify Documentation link appears for logged-in users even without a project selection;
API reference has no visible sidebar/Settings/setup link but legacy direct route remains.
Switch Laravel, Node.js, React and Next.js and inspect distinct actionable code blocks,
copy buttons and safe one-time secret handling. React instructions must not include a VITE_ key.
Run Vitest focused on AppShell, ProjectApiKeysPanel and DocumentationPages plus full
`scripts/verify.ps1`, then browser-check all four recipes, small screens and keyboard controls.
Manual M6.2/M6.3 browser acceptance remains pending independently.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 candidate tests: `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_infrastructure_api.py -v`; `docker compose exec -T web npm test --
--run`; then `./scripts/verify.ps1`. IR-001–IR-008 require foreign membership rejection before
ClickHouse, supported attrs only, absence/co-observation honesty, bounded window, truncation, live
authenticated OTLP persistence, UI empty/error/loading/truncated/project changes, no K8s
dependency, prior regressions. **None is marked accepted until the actual operator results are
reported**.

## Pre-M6.3 UI refinement — pushed; final acceptance pending

The compact header selectors, authorized project navigation and detail drawers are
implemented and visually approved. The final single-level card correction was committed
and pushed at `a4bcb4c`. The post-correction `scripts/verify.ps1` gate passed
on 2026-10-22 (170 backend, 50 frontend tests). Manual M6.2 browser
acceptance remains unreported. M6.3 stays blocked until it is recorded and
the closeout documentation is committed and pushed.
See `UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

## Verified final UI release gate — 2026-10-22

The operator ran 29 focused service catalog/detail tests successfully.
`scripts/verify.ps1` then completed on Windows/Docker with 170 backend tests
(one warning), 50 frontend tests in 11 files, Ruff lint/format, mypy (101
files), Django and migration checks, ClickHouse schema, ESLint, TypeScript,
Vite build and Git whitespace checks passing. The tested UI code commit was
`a4bcb4c`; documentation commit `fb36906` was subsequently pushed with a
clean `main`. This is automated verification, not manual browser proof.
See `M6_2_BROWSER_ACCEPTANCE.md` for the still-open browser gate.

## Historical M6.2/seeder automated gate (Windows/Docker, 2026-10-21)

The seeder completed for existing user `admin`, and its six focused tests passed. The
complete `scripts/verify.ps1` gate then passed: 170 backend tests, 44 frontend tests,
Ruff lint/format (101 source files), mypy (101 files), Django system/migration checks,
ClickHouse schema, ESLint, TypeScript, production Vite build and `git diff --check`.
Pytest reported one warning, no failures. Source commit `a0e7881` and demo seeder
commit `4b34f3c` are both pushed to `main` with the reported checkout clean.

Remaining manual proof is described in `M6_2_BROWSER_ACCEPTANCE.md`: real browser
Services catalog/detail, trace-link navigation, tenant/project switching and UI states.
Synthetic data is suitable for a browser walkthrough but does not replace an external
OTLP exporter or a foreign-user authorization test. M6.3 is not yet unblocked.

## V1 M6.1 historical quality gate

Run `docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_service_catalog_api.py -v`,
then Ruff check/format, mypy, Django system/migration checks, and `./scripts/verify.ps1`. Tests must
cover real foreign membership denied before ClickHouse, typed tenant predicates in every signal
subquery, the half-open 24h-default/7d-max window, empty-service and empty-environment behavior,
multi-signal merge, 500+1 truncation, generic `503` with closed client, and actual project-key OTLP
persistence across metrics/logs/spans for distinct tenants. Do not report M6.1 completed before the
full user environment and operational gates pass.

**Acceptance environment:** Windows 11 + PowerShell 7 + Compose services. Source of truth for detailed milestone matrices: `V1_MILESTONE_TESTING.md`, `V1_M2_MILESTONE_TESTING.md` through `V1_M5_MILESTONE_TESTING.md`.

## 1. Release gates

From repository root:

```powershell
.\scripts\verify.ps1
```

That runs Docker Compose config validation; backend pytest, Ruff lint/format, mypy, Django checks, migration drift, ClickHouse schema; frontend ESLint, `tsc`, Vitest, Vite build; and `git diff --check`. Do not mark a slice accepted if applicable gates fail.

Focused examples:

```powershell
docker compose exec -T api /opt/venv/bin/python -m pytest apps/alerts/tests/test_notifications.py -v
docker compose exec -T api /opt/venv/bin/ruff check .
docker compose exec -T api /opt/venv/bin/ruff format --check .
docker compose exec -T api /opt/venv/bin/mypy .
docker compose exec -T web npm run test -- --run
```

CI workflow `.github/workflows/ci.yml` runs backend lint/type/migration tests with PostgreSQL and frontend lint/type/tests/build; real Compose/ClickHouse/browser acceptance is **additional** local operational proof, not assumed covered by CI.

## 2. Mandatory test matrix per changed boundary

| Boundary | Positive | Negative/edge |
| --- | --- | --- |
| Auth | CSRF/login/session/logout | invalid login, anonymous mutation, CSRF missing |
| Tenancy | same-project read/write | **real foreign** org/project UUID 404 before ClickHouse; viewer 403 |
| Machine keys | valid scoped OTLP | revoked, expired, wrong scope, wrong scheme/key |
| OTLP | real exporter/protobuf, scoped durable row | bad wire, gzip corrupt, over limit, ClickHouse 503 |
| Metrics | raw scalar list/window | foreign UUID, histogram-only, empty, truncated, 503 |
| Logs | exact filters & metadata | malformed trace ID, missing ID, 503, boundary window |
| Traces | exact ID, parent, bounded results | missing parent, invalid ID, foreign ID, 503 |
| Dashboards | pin/render/remove using metrics API | cap, duplicates, viewer denial, source unavailable |
| Alerts | pending->firing->ok, no-data/error | duplicate same-state, ambiguity, stale evaluation, disabled |
| Webhooks | HMAC, 204, recovered | allowlist, secret redaction, retry/backoff, redirect, lease reclaim |
| UI | loading/empty/error, role and tenant switching | stale project cache, mutation errors, empty/truncated UI |

## 3. Operational smoke scripts

| Command | Proves |
| --- | --- |
| `./scripts/verify-m2.ps1` | secure key, real OTLP span, scoped ClickHouse durability |
| `./scripts/verify-m3.ps1` | real metric, session query, Metrics/Dashboards browser |
| `./scripts/verify-m4.ps1` | real correlated log/trace and browser navigation |
| `./scripts/verify-m5.ps1` | isolated project, signed firing/recovery, tenant isolation, Alerts browser, cleanup, full gate |

These may prompt for session credentials, create disposable control-plane records, and recreate containers **without destroying volumes**. For final milestone acceptance do not use optional skip switches. Never log/copy raw tokens or one-time signing keys into test reports. Unique emitted telemetry remains in ClickHouse.

## 4. Last observed V1 M5 acceptance

The completed M5 closeout reported **135 backend passed** (one warning), **35 frontend passed**, Ruff clean, mypy 93 files clean, Django/migration and ClickHouse schema valid, Vite build green, and the real webhook/browser verification passing. This is a historical result at `d43947a`, not a substitute for testing a later change.

## 5. Regression, release and commit protocol

Record: exact baseline SHA, targeted tests, full gate, human verification when required, documentation review, generated/secret file inspection, staged diff, commit SHA, push and clean status. If a regression occurs, stop release; produce a minimal patch against current tree and rerun impacted gates. Document the resolution in `Debugging.md` and `ProjectImplementation.md` when meaningful.

## 6. Planned M6 quality criteria

When accepted, M6 must include real OTLP evidence for observed services/resources/relationships, bounded tenant-first queries, no inferred health/dependencies, foreign-tenant negative cases, and real browser workspace proof. Consult `V1_M6_MILESTONE_TESTING.md` **only after** the planning patch exists in current Git state.

## 7. V1 M6 acceptance matrix — planned, not executed

| Slice | Required positive proof | Required negative proof |
| --- | --- | --- |
| M6.1 | Tenant-scoped discovery from real M/L/T rows, observed first/last timestamps | foreign real tenant `404` before CH, query bounds/limits, `503` versus empty |
| M6.2 | Existing signal explorers linked from service detail, real UI state | project switch/cache leakage, malformed filter, truncated/empty/error browser paths |
| M6.3 | Host/K8s fields from exact stored OTel attributes | missing/contradictory attribute rows, cross-tenant mixing, false resource inference |
| M6.4 | Two real cross-service spans correctly linked via parent ID | orphan parent, cross-trace/project, same-service parent, span links, false edges |
| M6.5 | Real OTLP integration → services/resources/relationships → browser; full gate | cleanup safety, no synthetic telemetry, real foreign-project non-discovery |

The detailed cases are in `V1_M6_MILESTONE_TESTING.md`; none are satisfied merely by adding documentation. Do not report test counts or a `verify-m6.ps1` execution until the actual program, command and results exist. M5's 135 backend / 35 frontend tests remain *historical evidence* from M5, not M6 acceptance. Continue testing each milestone only after its dependencies are verified, committed, pushed and the worktree is clean.

## M6.2 browser acceptance matrix (manual evidence pending; code tested)

1. Services sidebar link resolves within the authorized project URL; the same project UUID is passed
   through the catalog query API and React Query key.
2. The selected 1h/6h/24h/7d UTC window is passed as actual `start`/`end` with `limit=500`.
3. List/detail render exact service/environment, telemetry signal counts, and first/last observations.
4. Empty results mean *not observed*; server error remains a visible error; truncated results warn
   that missing rows cannot be interpreted as absent services.
5. Selected service URL is not tenant authorization; project changes query the new UUID and may not
   retain the previous project's catalog as current detail.
6. Explorer links retain project context, explicitly disclose that filters are **not** applied, and
   rely on existing Django tenant authorization.
7. No synthetic health, ownership, SLO, deployment, trace ID or service dependency appears.

Focused run: `npm run test -- ServicesWorkspace.test.tsx`, `npm run lint`,
`npm run typecheck`, `npm run build` in `frontend/` or the Compose `web` container. Finish with
`./scripts/verify.ps1` and a live Services browser smoke before commit/push.

### Pre-M6.3 flat layout acceptance

`ProjectWorkspacePage.test.tsx` checks for an unbordered shared layout without
removing the Overview's four independent data cards. The Services detail test
ensures the drawer's detail body is not another alert-style card. Browser-check
all project sections for redundant enclosing borders, clipping and spacing,
including small viewports. Finish with `scripts/verify.ps1` before commit.

Follow-up visual regression: `ServicesWorkspace.test.tsx` rejects boxed toolbar
classes; `ProjectWorkspacePage.test.tsx` continues to require an unbordered
workspace container. Browser-check absence of nested cards and duplicate route
titles across all eight project pages; rerun full frontend/release gates.

UI hierarchy correction: `ProjectWorkspacePage.test.tsx` checks one
Services content surface and sibling Overview fact cards without an outer
card. Browser-check Services, Metrics, Logs, Traces, Settings, Overview,
Dashboards and Alerts to ensure cards are visible but never nested.
Run lint, TypeScript, Vitest, build and full `scripts/verify.ps1`; manual
browser sign-off and a clean commit/push are still required.

## Linked documentation acceptance — pending

After adding links to project Settings, test that both writers and viewers see two links without a new project navigation tab. Verify `/docs/telemetry-setup` and `/docs/api-reference` render under the authenticated app shell, describe protobuf-only OTLP and session-versus-machine-key auth accurately, do not display or persist a real key, remain legible on narrow viewports, and return to the workspace. Run focused frontend component/page tests, lint, typecheck, build and `scripts/verify.ps1`. These checks and the separate M6.2/M6.3 browser matrices must be recorded before claiming acceptance.
