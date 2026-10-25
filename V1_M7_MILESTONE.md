# Sentrix V1 M7 — Guided Integrations and Verified Onboarding

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
