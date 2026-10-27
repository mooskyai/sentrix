# Sentrix V1 M7 — Integration Testing and Acceptance

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

## M7.3.3a — Next.js Node candidate testing (OPEN)

Starting GitHub baseline `5427d4f` already has passing M7.3.2 CI. For the
new Next.js candidate: run `npm install --package-lock-only` and review the
generated lock; `npm ci`, `npm run build`, `npm test`, `npm audit` in
`integrations/m7-nextjs-node`. Verify true Next.js App Router request and
real OTel SERVER span against fake protobuf receiver; reject 401, invalid
origin, CLI keys and missing stdin. Run strict Django tests for the bounded
`m7_next_readback` query, then perform a separate live direct exporter and
exact key-derived ClickHouse read-back; capture nonsecret run/trace/UTC.
Owner/nonmember HTTP 200/404, browser isolation, same-key revocation 401 and
`./scripts/verify.ps1` now passed as recorded above. Exact new CI remains OPEN.
Never substitute the Node/Express acceptance for Next.js evidence. See
`docs/M7_NEXT_RUNTIME_ACCEPTANCE.md`.

## M7.3.2 current acceptance checkpoint (2026-10-27; exact-SHA CI OPEN)

- [x] Direct real Node/Express SDK → authenticated OTLP → independent
  ClickHouse read-back for current primary demo project and exact trace.
- [x] Owner authorized read; separate `m732-nonmember` trace/catalog HTTP 404.
- [x] Three real-browser checks explicitly confirmed by the operator.
- [x] Revoked temporary key DB state and live OTLP HTTP 401 verified.
- [x] 365-day synthetic seeding in both demos; **not real SDK evidence**.
- [x] Latest local gate: 290 backend, 103 frontend, Ruff/mypy/schema/build.
- [ ] Final reviewed commit, push, exact-commit GitHub CI and release sign-off.

Full current run IDs and timestamps: `docs/M7_3_2_FINAL_ACCEPTANCE_2026_10_27.md`.
The dated 2026-10-26 tests below remain historical, not current gate status.

## Local year-history seeding is not M7.3.2 evidence

The opt-in `seed_demo_year --username admin --days 365 --create-nonmember`
command exercises 365 daily synthetic metric/log/span snapshots in reserved demo
projects and creates a nonmember account for later authorization testing.
The synthetic history and account creation alone cannot close any SDK, browser,
foreign-user HTTP 404, key revocation, or CI gate. See `docs/DEMO_YEAR_SEED.md`.

## M7.3.2 — direct Node SDK technical gate VERIFIED; final gates OPEN (2026-10-26)

- **ND-001/ND-002/NF-001/NF-002:** Direct upstream Node/Express SDK generated
  chunked protobuf request (1,041 bytes; no Content-Length); Uvicorn ASGI
  started successfully after replacing development WSGI serving.
- **ND-004/ND-005/NF-003:** Direct SDK span independently read from tenant-key
  scoped ClickHouse: project `07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`,
  run `ddbaab4290524f2092254fb23ff01613`, trace
  `2f06c0b95492feea6379d231993c5b5d`, UTC `2026-10-26T08:25:53.243Z`.
- **NF-004:** Rebuilt container gate: **277 backend passed (1 warning), 103
  frontend passed, 4 Node tests passed; npm audit 0 vulnerabilities; Ruff,
  format, mypy 124, Django, ClickHouse and production build passed.**
- **ND-006/ND-007 (OPEN):** Actual signed-in browser observation, separate
  foreign-user 404, revoked-key HTTP 401, credential cleanup, approval,
  post-change gate, committed SHA, push and exact-SHA GitHub CI.
- **Auxiliary API smoke (NOT YET RUN):** `m7_node_auth_smoke.py` checks owner
  persisted trace and catalog plus existing nonmember's API 404 through DRF;
  this is not an actual browser-session test. See operator closeout guide.

## M7.3.2 — direct SDK chunked-body regression and acceptance (candidate)

- **NF-001:** Check whether unmodified `probe.cjs` uses HTTP Transfer-Encoding
  chunked without Content-Length; output only safe transport header names and
  the protobuf byte count, no secrets or payload.
- **NF-002:** The local Docker API runs the existing Uvicorn ASGI application;
  an unreadable chunked body fails with 400, not misleading OTLP 200.
- **NF-003:** After controlled API recreation, the same temporary scoped key
  must produce a **direct** real Express SDK span and an exact tenant-scoped
  ClickHouse match; a relay-only pass does not close this requirement.
- **NF-004:** Run focused/backend/frontend/Node test gates; preserve browser,
  separate-user 404, revoked-key, teardown, review, commit/push/CI gates.
- **Observed before this correction:** a relay-forwarded SDK span was durable,
  but independent read-back of subsequent direct Node export still found zero.
  Root cause remains **hypothesized** until transport inspection + operator
  direct persistence re-test. No milestone acceptance claimed.

## M7.3.2 — real Node wire diagnostic (candidate; not yet executed)

- **ND-011:** A real Express process sends exactly one OTLP protobuf SERVER
  span through an in-memory loopback relay to the actual Sentrix receiver.
- **ND-012:** The same captured wire bytes must produce one SDK span and one
  normalized row in the production Django decoder. A resource-only envelope
  with zero leaf spans, wrong trace, or corrupt protobuf fails closed.
- **ND-013:** The original temporary write key authenticates independent
  ClickHouse read-back. Do not accept HTTP 200, fake receivers or normalized
  in-memory rows as durable persistence.
- **Observed:** live Node HTTP 200 twice but exact project read-back zero;
  prior Django trace persisted. Synthetic Node-like demo data passed the
  separate 24h project/secondary-isolation diagnostic. Full local release gate
  passed 271 backend and 103 frontend tests before this diagnostic candidate.
  **New diagnostic tests, live rerun and all acceptance gates: pending.**

## M7 synthetic demo seed coverage — not runtime acceptance

- **ND-SEED-01:** Synthetic primary demo service `demo-node-express` / `integration`
  has metric/log samples and a distinct, explicitly marked HTTP SERVER span.
- **ND-SEED-02:** The secondary demo tenant has no Node demo identity; the old
  gateway/checkout/payments trace parent chain remains unchanged.
- **ND-SEED-03:** Fresh seeder run must pass scoped OTLP ingestion/read-back
  without leaking or persisting plaintext keys; record its independent result.
- **ND-SEED-04:** Real `m7-node-express-runtime` with exact SDK run ID and
  `sentrix.acceptance.run` remains absent from operator project despite HTTP
  export acceptance. Seed rows **must not** satisfy ND-005 or close M7.3.2.

## M7.3.2 operator check — partial (2026-10-25)

- Baseline v2 patch: applied without error; static preflight Ruff/format/mypy
  passed, focused Python verifier 21/21 passed, full release gate 271 backend
  and 103 frontend passed including schema/build checks.
- Isolated Node `npm test`: **3 passed, 1 failed**, from a test protobuf
  schema incorrectly declaring Span timestamps `uint64`. Corrected to
  `fixed64` (OTLP wire type 1) and added monotonic decoded timestamp checks.
  **Repeat Node test: NOT YET REPORTED.**
- npm audit: two moderate findings were reported by installer; review the
  exact dependency chain and commit the verified lockfile before signoff.
- Independent real Sentrix exporter, read-back, browser/security acceptance,
  key cleanup, commit/push and post-correction CI: **NOT YET VERIFIED**.

## M7.3.2 test matrix — CANDIDATE, operator gates OPEN

- **ND-001:** Start real Express process with Node SDK before framework load; make HTTP `GET /checkout`.
- **ND-002:** Fake receiver decodes genuine OTLP protobuf; check POST, type, Bearer, trace/run, SERVER, resource and HTTP method/route.
- **ND-003:** Reject insecure remote URL, URL secrets, CLI key and missing key; reject OTLP 401/500 without false success.
- **ND-004:** Scoped key-derived read-back uses UUID/UTC typed bounds and two-row limit; reject empty, duplicates, malformed, wrong project/service/trace/attributes/time.
- **ND-005 (operator):** Review/generated locked dependency tree; repeat actual live SDK export and independent stored trace read-back.
- **ND-006 (operator):** Independently verify browser foreign-user 404, UI trace/service evidence, revoked/expired key, no secret leakage and teardown.
- **ND-007 (operator):** Ruff-first and full `scripts/verify.ps1`, clean commit/push, exact-SHA CI, nonsecret evidence and approval.

No M7.3.2 acceptance is recorded. M6, M7.1, M7.2 and outstanding M7.3.1 human gates remain OPEN.

## M7.3.1 runtime/persistence evidence — VERIFIED, full acceptance OPEN

- **DJ-009:** Known UTC ClickHouse `DateTime64(9)` naive datetime results
  are interpreted as UTC only for the defined span columns, preserving the
  exact bounded evidence window and increasing endpoint order.
- **DJ-010:** Regression tests reject out-of-window, non-datetime, duplicate
  and mismatched spans; after correcting the first read-back's naive UTC
  handling, the operator independently reran it and received **persistence
  VERIFIED** for the actual stored Django WSGI server span.
- **Run evidence (2026-10-25):** project
  `07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`, run
  `3ac7ac6765ea487cbd5de61b32bb1090`, trace
  `06b5945cf479625c5a7a051bb748ca3a`, producer time
  `2026-10-25T08:18:57.946820+00:00`, service/environment
  `m7-django-runtime` / `integration`.
- **Full operator release gate:** 250 backend pytest and 102 frontend Vitest
  passed; Ruff lint/format, strict mypy (120 files), Django and ClickHouse
  checks, ESLint, TypeScript and production build passed.
- **Still NOT RUN / NOT RECORDED:** foreign-user browser 404, same-trace UI
  evidence, keyboard/mobile, temporary credential revocation, other frameworks,
  exact pushed-SHA CI and final operator sign-off. M6 and M7.1/M7.2 manual
  gates remain open independently.

## M7.3.1 test and operator acceptance — AUTOMATED PASS; OPERATOR PARTIAL

- **DJ-001:** Dedicated Django WSGI subprocess serves `/checkout/` over real
  HTTP, emits one manually instrumented SDK `SERVER` span with nonzero trace ID.
- **DJ-002:** Local fake OTLP receiver observes actual POST protobuf at
  `/v1/traces`, correct service/environment/run labels and Bearer header.
- **DJ-003:** Read-back SQL derives typed org/project IDs from authenticated
  key; enforces exact service/env/run/time and a strict 2-row cap.
- **DJ-004:** Missing, repeated, malformed, unrelated span, trace ID, timing
  or run marker fails closed; wrong project cannot pass the read-back.
- **DJ-005:** Reject nonlocal cleartext origin, URL userinfo/query and leaked
  secrets; no browser ingestion key or unmanaged control-plane session.
- **DJ-006 (operator):** Run Django SDK producer with masked temporary key;
  verify the same trace via independent ClickHouse read-back and in Services/
  Traces browser; record sanitized IDs, versions and timestamp.
- **DJ-007 (operator):** Separate user without membership gets 404 before
  ClickHouse, empty/failure/timeout outcomes are truthful, key is revoked.
- **DJ-008:** Full Docker `scripts/verify.ps1` + exact-SHA CI, documentation
  synchronization, clean commit/push and evidence sign-off recorded.

Focused command: `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_m7_django_runtime.py -v`.
See `docs/M7_DJANGO_RUNTIME_ACCEPTANCE.md`. Manual M6 and M7.1/M7.2 checks
stay open until independently observed; no automatic SDK certification.

## M7.2 automated and operator acceptance — NOT RUN

| Case | Expected result |
| --- | --- |
| GIN-001 | Host/Compose origins resolve correctly; remote accepts only HTTPS root without credentials/paths |
| GIN-002 | Service/environment fields reject quotes, whitespace, shell and multiline injection |
| GIN-003 | Django CLI and Node SDK recipes export traces to OTLP/HTTP protobuf with server-only placeholders |
| GIN-004 | No browser key entry/storage; no query until user requests a service check |
| GIN-005 | Exact project/service/environment match; nonmatching row not shown as connected |
| GIN-006 | Bounded UTC 24h catalog query; empty, truncated and failure states remain distinct |
| GIN-007 | Framework/input/project change never displays stale other-service evidence |
| GIN-008 | Full `scripts/verify.ps1` (backend/frontend/tests, Ruff, mypy, build, schema) |

Manual operator: apply from clean SHA; run a real Django process and a real
Node/Express process with temporary *server-only* project key and collect
nonsecret runtime/SDK versions, exact service/environment, signal times and
actual ClickHouse/browser comparison. Verify no key in DevTools, no unexpected
ingest from the browser, secure remote origin validation, wrong-project data
isolation, truncated/503 states, keyboard/narrow view and key revocation.
Record CI for pushed SHA, unresolved deviations and operator approval here.
A passing mocked test or historical acceptance producer is **not** a real
framework runtime certification. Keep M6/M7.1 browser gates open.

Commands:

```powershell
docker compose exec -T web npm run test -- --run src/guidedIntegration.test.ts src/components/GuidedIntegrationPanel.test.tsx
.\scripts\verify.ps1
```

**State:** M7.1 implementation candidate. No M7 runtime/operational
acceptance has been recorded. The M6 browser gates remain open independently.

## M7.1 automated matrix

| Case | Expectation |
| --- | --- |
| INT-001 | Project viewer reads observed metrics/logs/spans and exact UTC 24h window |
| INT-002 | All three queries use typed organization/project UUIDs from Django membership |
| INT-003 | Separate foreign user and missing project return 404 without opening ClickHouse |
| INT-004 | Anonymous request denied; Bearer machine key is not a read-session substitute |
| INT-005 | Empty window returns `not_observed` and null timestamps; not unhealthy |
| INT-006 | Any ClickHouse error or malformed summary returns sanitized 503; client closes |
| INT-007 | Fixed 24h, max row-read and execution limits; no client time/tenant/table input |
| INT-008 | Settings panel handles loading, partial signals, empty, 503, refetch, switching |
| INT-009 | No browser API keys or arbitrary raw telemetry in the diagnostic response |
| INT-010 | Full `scripts/verify.ps1` including backend/frontend/live schema and build |

## Operator acceptance — NOT RUN

1. From a clean pushed baseline and healthy Compose, instrument a real
   server process/Collector with a temporary project-specific key stored only
   on the server. Record safe SDK version/endpoint/runtime.
2. Send a real workload, independently query ClickHouse; in project Settings
   click **Check again** and compare per-signal counts/timestamps, including
   a partial-signal project and an empty time window.
3. Sign in as another independent user without project membership and request
   the route directly: require 404 and no ClickHouse query. Switch an authorized
   project in browser and ensure stale query data does not persist.
4. Safely induce ClickHouse query failure (503), check recovery and keyboard/
   narrow viewport. Verify no raw key is sent in any browser request.
5. Revoke temporary credential; record full gate and GitHub CI; update
   `MILESTONE_ACCEPTANCE_CHECKLIST.md`, README and implementation evidence.

Use:

```powershell
docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_connection_diagnostics_api.py -v
docker compose exec -T web npm run test -- --run src/components/ConnectionDiagnosticsPanel.test.tsx
.\scripts\verify.ps1
```

## Release decision

**M7.1: OPEN.** No framework runtime is certified, and M6 human acceptance
is not retroactively completed by successful M7 automated checks.
