# Sentrix V1 M7 — Guided Integrations and Verified Onboarding

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

## M7.3.3a candidate — real Next.js App Router Node request

M7.3.2 is now pushed on `main` at `5427d4f` and exact-SHA GitHub Actions
workflow `40451690954` concluded successfully on 2026-10-27. The next isolated
work is a Next.js 16.4.3 Node App Router fixture (no Edge/browser key), manual
OTel SERVER span, real binary protobuf SDK export, fake receiver negative cases
and bounded authenticated ClickHouse read-back. No new Sentrix API, migrations,
React write key, or storage. Real Next.js SDK/ClickHouse proof, owner/nonmember authorization, browser
attestation, key revocation and local verification have since passed. The
fixture remains **unreleased** until lockfile review, commit and own CI pass.
See `docs/M7_NEXT_RUNTIME_ACCEPTANCE.md`. Laravel/PHP and Collector follow
as distinct implementation and acceptance slices.

## M7.3.2 local Node.js runtime/security acceptance (2026-10-27)

Direct Node.js/Express runtime persistence, independent tenant read-back,
owner/foreign-user 200/404 checks, revoked key 401, and three operator-reported
browser checks passed. The 365-day synthetic data fixture is separate from
SDK evidence. Final reviewed commit, push and exact-SHA GitHub Actions CI remain
required before M7.3.2 release sign-off and starting M7.3.3. See
`docs/M7_3_2_FINAL_ACCEPTANCE_2026_10_27.md`.

## M7 demo integration UI data (synthetic, independent of M7.3.2 proof)

`seed_demo` creates optional, unmistakably synthetic `demo-node-express`
metrics, logs and an independent HTTP server span for project UI walkthroughs.
It does not create a Node runtime process or resolve the real Express missing
persisted-span failure. Keep M7.3.2 implementation and operator acceptance
blocked until exact SDK trace/read-back, browser/foreign-user and key teardown
checks succeed.

## M7.3.2 candidate — Node.js/Express live SDK export

Create real isolated Express `GET /checkout` traffic with NodeSDK started
before framework import and one manually marked `SERVER` span. Send OTLP
binary protobuf to the existing receiver using a stdin-only scoped key.
Independently check one exact stored span in key-derived `sentrix_spans`
with UTC/tenant/marker/HTTP identity. No arbitrary external Node project
certification, automatic instrumentation or global M7.3 sign-off.
M7.3.3 remains blocked on verified/pushed M7.3.2 acceptance.

## M7.3.1 implementation slice — Django/Python manual span export

Build an independent minimal Django WSGI service and generate one actual
HTTP `/checkout/` request. The real OpenTelemetry Python SDK manually records
one `SERVER` span with service `m7-django-runtime`, environment `integration`
and a unique run marker, posting OTLP/HTTP protobuf to the selected project.
A second CLI authenticates the same temporary project key in Django/PostgreSQL,
then checks a bounded ClickHouse query for exactly one correlated span.
Regression tests cover the isolated Django-to-fake-receiver wire path, scoped
SQL, limits and malformed evidence. No production lockfile changes.
Actual run, persistent read-back, foreign-user session denial, browser UI,
revoke/teardown, CI and reviewer sign-off remain mandatory. This does not
constitute automatic instrumentation, arbitrary Django-app certification or
completion of the wider M7.3 matrix.

## M7.2 implementation — guided Django/Python and Node.js server exporters

**Baseline:** committed `4116f087127575a8218d85708932ef1448262361`.
M7.1 code/full local gate is complete (233 backend, 87 frontend reported),
its browser/external-app acceptance remains open; M6 manual acceptance is open.
M7.2 adds Settings-based Django/Node recipes without new ingestion interfaces.
Operator chooses Windows host `http://localhost:8000`, same Compose network
`http://api:8000`, or a user-entered HTTPS root origin; unsafe origins and
service/environment snippet injection are rejected. All copied code is
server-only and placeholder-based, never project credentials.

After actual app traffic, an explicit **Check service** calls the existing
member-authorized Services catalog with UTC 24h and maximum 500 entries,
matching exact service and environment. Presence is historical telemetry,
not connection health. No result means no matching row in the returned window;
when truncated or query failed it is **inconclusive**, not a disconnection.
Recipes emit traces only; no new backend query endpoint, migrations, key
validation, browser OTLP or automatic polling. Django/Node real-runtime smoke
and version certification remain M7.3 work. M7.2 is not accepted until its
operator tests and clean committed release gate are recorded.

**State: planned milestone with an M7.1 implementation candidate (not accepted).**
Baseline reviewed: `16c94afdbbc5d5cfaf107760d3559ecc795d6143`.
M6.2/M6.3/M6.4 operator browser and independent foreign-user acceptance is still open.

## 1. Goal and boundary

Help a project member configure a real external exporter and determine whether
Sentrix has stored any of its recent OTLP telemetry. Show observations rather
than inventing connected/healthy status; ingestion credentials remain server-side.
All project reads require Django sessions and organization membership before
any ClickHouse client is opened. No browser OTLP Bearer key or new storage.

## 2. Ordered slices

- **M7.1 — First telemetry observations:** fixed 24h project-specific counts
  and latest timestamps for metrics/logs/spans; accessible on-demand Settings
  panel; truthful empty, loading and 503 states.
- **M7.2 — Exporter environment guidance:** context-safe host, Compose and
  remote HTTPS endpoints, validated copyable recipes and explicit failure codes.
- **M7.3 — Runtime verification:** real process tests for Python/Django,
  Node/Express, Next.js Node, Laravel and OTel Collector, each with concrete
  versions/signals/nonsecret evidence. Browser instrumentation is out of scope.
- **M7.4 — Integration closeout:** multi-signal, membership, adverse-path,
  keyboard/browser, secret handling, full release gate, docs and operational
  sign-off. Do not claim upstream SDK behavior as locally tested until proven.

## 3. M7.1 contract

`GET /api/v1/projects/{project_id}/integrations/connection-status/` uses the
browser's session and current project membership, not a project ingest key.
Django selects `[now - 24h, now)` in UTC. Existing ClickHouse tables provide
`count()` and latest timestamp for each signal; reads are typed, bounded to
250000 source rows / eight seconds each, and close the client on all paths.
The response provides `project_id`, `start`, `end`, `observation_state` and
`signals` with `metrics`, `logs`, `traces` each `{observed,count,last_seen}`.
An empty window is `not_observed`, not disconnected. Missing/foreign project
returns 404 without ClickHouse, an unauthenticated session returns 401/403,
query failures return sanitized 503. No raw payloads, key values or health
predictions are exposed. No migrations or background polling.

## 4. Acceptance

M7.1 is accepted only after focused/full automated tests, real external
OTLP/ClickHouse and browser checks, independent-user denial, proof no raw key
reaches the browser, and recorded operator evidence. A code patch or 200 API
response alone does not complete integration onboarding. See
`V1_M7_MILESTONE_TESTING.md` and `MILESTONE_ACCEPTANCE_CHECKLIST.md`.
