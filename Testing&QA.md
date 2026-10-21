# Sentrix — Testing and Quality Assurance

## Pre-M6.3 UI refinement (pending acceptance)

Against clean pushed `8b8d3fd`, the application shell consolidates organization/project
selection into the header; project links are withheld until both valid selections exist, and
Services/Logs/Trace span inspection uses a right drawer. Compact spacing is a presentation
change only. Validation and operator steps are recorded in `UI_DENSITY_AND_DRAWERS.md`.
Do not treat this proposal as passed, committed or a new infrastructure milestone until the
full release gate, browser acceptance and clean push are documented.

## Verified M6.2/seeder automated gate (Windows/Docker, 2026-10-21)

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
