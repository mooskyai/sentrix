# Sentrix — Master Milestone Acceptance Checklist (M1–M12)

## M7.1 candidate sub-gate — NOT ACCEPTED

- [ ] **M7.1-D01:** A signed-in member reads only the correct project's
  24h metrics/logs/traces observations; verify rows and timestamps against
  independent ClickHouse/OTLP evidence.
- [ ] **M7.1-D02:** Different unauthorized user and unknown project return
  nondisclosing 404 without opening ClickHouse.
- [ ] **M7.1-D03:** No-data, 503, partial-signal, keyboard/mobile and
  project-switching behavior observed in browser, without invented health.
- [ ] **M7.1-D04:** Instrument a real server/Collector externally and confirm
  the expected signal in the correct project without browser-side write keys.
- [ ] **M7.1-D05:** Focused/full verification, CI, operator/date/run evidence,
  affected documentation, commit and clean `main` recorded. M6 acceptance
  remains independently open.

**Type:** Release and operator-evidence checklist; **not** a claim that any unchecked feature has shipped.
**Reference baseline:** GitHub `main` at `61161bd3fb2da859ac1f6636a71e5daccbff6e02` (2026-10-25).
**Sources of truth:** existing `V1_MILESTONE*.md`, `V1_M2_MILESTONE*.md` through
`V1_M6_MILESTONE*.md`, `M6_2_BROWSER_ACCEPTANCE.md`, `M6_3_BROWSER_ACCEPTANCE.md`,
`M6_4_BROWSER_ACCEPTANCE.md`, `ROADMAP.md`, and release evidence in `ProjectImplementation.md`.

This is the **index of proof required** before a milestone is declared accepted. Detailed
contracts and case IDs in the linked milestone testing plans remain authoritative. Use
this file across all milestones and open a **separate dated evidence entry** for every
new acceptance run; do not turn historical or proposed work into a new acceptance claim.

## 0. How to record an honest result

For every item use **PASS / FAIL / BLOCKED / NOT RUN / N/A** in the evidence entry.
A Markdown checkbox is a tracking aid only: mark `[x]` only when its corresponding
result is PASS with reproducible evidence. A passing unit suite, HTTP 200, or an
agent-generated patch alone does **not** satisfy live browser or security requirements.

- **Historical acceptance**: M1–M5 and M6.1 are recorded as previously accepted
  in repository milestones. Do not retroactively change their records without new
  observed evidence; run their regression gates when later changes touch them.
- **Implemented but operator-open**: M6.2–M6.4 and overall M6 closeout. M6.5's
  read-back implementation and a recorded telemetry run are verified, but do not
  close the missing browser, independent-user, actual external app, retries,
  revocation and cleanup gates.
- **Planned**: M7–M12. Their checklists are **provisional**, not evidence of code,
  approved acceptance specifications, supported SDKs, deployment or release dates.
- **Separate acceptance from delivery**: a feature may be implemented, tested,
  committed and pushed while human/operator acceptance remains open. Record both.
- **No secrets**: record nonsecret IDs, exact SHA, timestamp/timezone, CI links,
  sanitized status/error codes and screenshots; never include a raw project key,
  session cookie, webhook signing secret, user password or telemetry payload.

### Universal gate — repeat for every implemented milestone and submilestone

- [ ] **Scope:** approved contract, explicit out-of-scope boundaries and versioned
      baseline are recorded; no adjacent milestone is silently implied.
- [ ] **Security:** authenticated project membership/RBAC is enforced before
      data-plane reads; foreign user/project denied without query; session/CSRF
      and server-only `telemetry:write` key boundaries hold where applicable.
- [ ] **Correctness:** positive, negative, time-boundary, empty, error, limit and
      truncation cases have runnable evidence; data is not fabricated.
- [ ] **Operational:** real dependency/instrumented producer or an explicitly
      declared scoped substitute has been exercised; failures and cleanup noted.
- [ ] **Browser:** desktop/mobile navigation, keyboard and focus, loading/empty/
      error states and tenant switching are manually checked for UI slices.
- [ ] **Repository:** `scripts/verify.ps1` passes (pytest, Ruff check/format,
      mypy, Django/migrations/schema, ESLint, TypeScript, Vitest, build); CI
      success is attached for the exact pushed SHA.
- [ ] **Documentation:** review the 14 documentation roles in `AGENTS.md`; update
      affected README, architecture/API/security/setup, implementation register,
      active milestone/test plans and acceptance records together with code.
- [ ] **Release:** sanitized evidence and open deviations are recorded, approval
      is explicit, temporary credentials revoked, no unintended data deleted,
      and `git status -sb` is clean with `HEAD == origin/main` after push.

A **BLOCKED/NOT RUN** mandatory gate prevents **accepted** status. If a check is
N/A, document the reason; never use N/A to bypass an actual security boundary.

## 1. V1 M1 — Platform Foundation (historically accepted)

Detailed source: `V1_MILESTONE.md`, `V1_MILESTONE_TESTING.md`.

- [ ] M1-PF-01: Python/Django, React/TypeScript, Compose, PostgreSQL, Redis and
      ClickHouse bootstrap is repeatable; health/readiness report actual dependency states.
- [ ] M1-PF-02: authentication, login/logout/session and CSRF protection work;
      anonymous requests do not gain management access.
- [ ] M1-PF-03: organizations, membership, projects, duplicate/invalid inputs,
      and owner/admin/editor/viewer actions honor the documented RBAC matrix.
- [ ] M1-PF-04: a **separate user** cannot enumerate or operate on foreign
      organizations/projects; project IDs/slugs do not grant access.
- [ ] M1-PF-05: React app navigation, empty states, permission-dependent actions,
      no leaked secrets, and database migration/fresh startup are verified.
- [ ] M1-PF-06: M1 quality gate, runtime smoke, docs and recorded release decision
      match the original acceptance entry; any new regressions are recorded.

## 2. V1 M2 — Telemetry Ingestion Foundation (historically accepted)

Detailed source: `V1_M2_MILESTONE.md`, `V1_M2_MILESTONE_TESTING.md`.

### M2.1 — Project API key control plane
- [ ] M2-1: writer creates a project key with one-time secret; viewer/foreign
      member cannot manage it; list/redaction/revocation and expiry work.

### M2.2 — Machine authentication boundary
- [ ] M2-2: Bearer format, key hash/prefix, scope `telemetry:write`, revoked/
      expired/invalid key cases return correct denial without tenant leakage.

### M2.3 — OTLP/HTTP ingestion gateway
- [ ] M2-3: `/v1/traces`, `/v1/metrics`, `/v1/logs` accept **protobuf** from
      an authenticated producer; wrong content-type, malformed payload,
      oversized/unsupported requests and 401/403/415 paths behave as documented.

### M2.4 — ClickHouse telemetry schema
- [ ] M2-4: live ClickHouse tables `sentrix_metrics`, `sentrix_logs`,
      `sentrix_spans` match versioned schema, sort/partition keys and columns;
      migration/bootstrap is idempotent.

### M2.5 — End-to-end ingestion persistence
- [ ] M2-5: real OTLP producer writes all three signals under credential-derived
      organization/project UUIDs; stored timestamps, IDs and attributes match.
      Foreign tenant's same identifiers never appear in another project's reads.

### M2.6 — API key management UI
- [ ] M2-6: project Settings displays safe metadata; raw key appears only at
      creation; read-only roles cannot mutate; revoke has clear feedback.

### M2.7 — Operational verification
- [ ] M2-7: fresh Compose/host-network run, invalid-key/format/failure paths,
      read-back and safe key teardown are recorded; `verify-m2.ps1` and complete
      quality/CI gates pass with milestone documentation and clean Git.

## 3. V1 M3 — Metrics Explorer and Dashboards (historically accepted)

Detailed source: `V1_M3_MILESTONE.md`, `V1_M3_MILESTONE_TESTING.md`.

- [ ] M3.1 — authorized, parameterized and bounded metrics catalog/series
      reads; correct shapes, units, exact service/environment, max-window,
      truncation, 404/503 and live tenant isolation.
- [ ] M3.2 — Metrics explorer renders only observed numeric points, honest
      non-scalar handling, filters/time window, errors/empty state, proper
      project switch and no invented rates/percentiles.
- [ ] M3.3 — project dashboard panel create/list/delete is role-scoped, stores
      configuration in PostgreSQL only, reads live ClickHouse series, and
      honors filter and project isolation.
- [ ] M3.4 — genuine metric point and dashboard read-back, browser smoke,
      `verify-m3.ps1`, full release gate, docs, CI and acceptance record.

## 4. V1 M4 — Logs and Trace Correlation (historically accepted)

Detailed source: `V1_M4_MILESTONE.md`, `V1_M4_MILESTONE_TESTING.md`.

- [ ] M4.1 — membership-first log search with bounded UTC window, typed severity,
      body/service/trace filters, valid ID handling, limit and 404/503 semantics.
- [ ] M4.2 — Logs explorer displays actual log rows/severity, exact filters,
      raw attributes, loading/no-data/error/truncation and safe inspection drawer.
- [ ] M4.3 — trace lookup requires actual nonzero trace ID; spans, parent IDs,
      duration and status are raw observations; log→trace links retain project
      and bounded window without introducing foreign access.
- [ ] M4.4 — real correlated OTLP log/span producer, independent session read,
      multi-project denial, `verify-m4.ps1`, keyboard/browser evidence and
      full tests/docs/CI/release decision.

## 5. V1 M5 — Alerting (historically accepted)

Detailed source: `V1_M5_MILESTONE.md`, `V1_M5_MILESTONE_TESTING.md`.

- [ ] M5.1 — project-scoped rule CRUD and typed comparator/threshold validation;
      viewer read-only, writers authorized, foreign project 404.
- [ ] M5.2 — real numeric query drives pending/OK/firing/no_data/error states;
      explicit evaluation time, stale writes and configuration changes are safe.
- [ ] M5.3 — Alerts UI reports stored state honestly, role-aware edits,
      enable/disable/delete, refresh and errors without browser-side evaluation.
- [ ] M5.4 — webhook channel authorization/redaction, signing, safe egress,
      outbox delivery, retry and deduplication/recovery are proven without
      leaking credentials or invoking unimplemented schedulers.
- [ ] M5.5 — isolated real OTLP firing→recovery run, one signed delivery per
      transition, expected HTTP receiver results, `verify-m5.ps1`, fixture
      cleanup and full release/CI evidence.

## 6. V1 M6 — Services, Infrastructure and Relationships (acceptance OPEN)

Detailed source: `V1_M6_MILESTONE.md`, `V1_M6_MILESTONE_TESTING.md`.
**Separate operator records:** `M6_2_BROWSER_ACCEPTANCE.md`,
`M6_3_BROWSER_ACCEPTANCE.md`, `M6_4_BROWSER_ACCEPTANCE.md`.

### M6.1 — Service catalog foundation (historically accepted)
- [ ] M6-1: service identity is exactly `(service_name, environment)`;
      tenant-first, time-bounded metrics/logs/spans aggregates have real counts,
      honest empty/limit/truncation and 404/503 behavior.

### M6.2 — Services workspace (implemented; browser acceptance open)
- [ ] M6-2A: same authorized project shows actual acceptance gateway,
      checkout, payments and exact `acceptance` environment and signal counts.
- [ ] M6-2B: Inspect returns observed metric names, recent logs, trace IDs;
      selected service/context survives Metrics, Logs and Traces deep links.
- [ ] M6-2C: explicit empty environment, no-data/error/truncation,
      drawer Escape/close/focus, desktop/mobile and stale project switching
      are inspected in the actual browser.
- [ ] M6-2D: a separate nonmember user receives 404 for foreign service
      catalog/detail; no ClickHouse query is executed for the forbidden project.

### M6.3 — Infrastructure (implemented; browser acceptance open)
- [ ] M6-3A: exact `host.name`, `k8s.cluster.name`, namespace, pod and container
      labels and metric/log/span counts are observed together on each resource.
- [ ] M6-3B: missing/empty attributes create no fictional inventory; no
      Kubernetes API, collector, background poller or health/status claim
      is inferred from synthetic resource labels.
- [ ] M6-3C: 24h default/7d limit, 1–500 result bounds, truncation,
      503, nonmember 404, window changes, mobile/keyboard and project switch
      pass the IR-001–IR-008 matrix with evidence.

### M6.4 — Observed service map (implemented; browser acceptance open)
- [ ] M6-4A: recorded trace's parent and child spans prove exactly
      `gateway → checkout → payments` for the three-service producer run.
- [ ] M6-4B: sample trace link, correct environments and selected project;
      unrelated trace IDs, orphan/ambiguous/same-service spans yield no invented edges.
- [ ] M6-4C: scan and result truncation, empty, failure, foreign project
      404 and UI/keyboard checks pass SM-001–SM-008; no cached graph is implied.

### M6.5 — Operator verification and milestone closeout (implementation pushed; acceptance open)
- [x] M6-5A: independent read-only ClickHouse read-back **reported passed**
      2026-10-25 on project `07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`,
      run `319b34b2346645fe8729b5518ca8a236`, trace
      `29b8393d3bef43d191ebc371b0113e26`: three signals, three spans,
      two parent edges and co-observed host/pod attributes.
- [x] M6-5B: implementation gate **reported passed** (224 backend, 82 frontend,
      Ruff/mypy/schema/build) and GitHub Actions succeeded on `61161bd`:
      https://github.com/mooskyai/sentrix/actions/runs/40162534351.
- [ ] M6-5C: independent user without project membership receives 404 on
      populated project query routes without opening ClickHouse.
- [ ] M6-5D: genuinely instrumented framework application or Collector
      produces accepted OTLP; record versions/network route and signal coverage.
      Controlled smoke's synthetic Kubernetes labels do not prove live K8s.
- [ ] M6-5E: invalid credential/scope/wire format, retry/ingestion failure,
      dependency outage, bounded read, recovery, truncation and no-fabrication
      cases are recorded with nonsecret evidence.
- [ ] M6-5F: operator completes browser checks for M6.2–M6.4 and records
      accessible desktop/mobile/keyboard and project-switch behavior.
- [ ] M6-5G: temporary key revoked; temporary control-plane fixtures safely
      cleaned; preserve regular raw telemetry unless retention policy applies.
- [ ] M6-5H: all three M6 browser records, M6 test plan, roadmap, README,
      implementation register, complete release gate and CI are synchronized,
      explicitly approved, committed/pushed and Git clean.

**M6 is NOT accepted** until M6-5C through M6-5H and all mandatory M6.2–M6.4
operator tests pass; the `[x]` entries document only the two scoped facts shown.

## 7. Planned milestones M7–M12 — PROVISIONAL gates, not delivered

Use `ROADMAP.md` for ordering. Before development, split each M7–M12 item
into separately versioned implementation, API/security and testing plans with
bounded user outcomes, operator scenarios and acceptance owners. Do not mark
these checks PASS until corresponding code and real evidence exist.

### M7 — Guided integrations and verified onboarding (PLANNED)
- [ ] M7-01: versioned server-side Django/Python, Node/Express, Next.js Node,
      Laravel/PHP and Collector quickstarts match tested runtime/SDK versions.
- [ ] M7-02: Docker/host/remote HTTPS endpoint selection, server-only secret
      handling and safe browser warnings are exercised end to end.
- [ ] M7-03: first received signal and timestamp are verified **per runtime**;
      missing signals, 401/403/415/503, invalid credentials and network
      diagnostics are actionable without exposing raw keys.
- [ ] M7-04: tenant/role tests, fresh environment, teardown, browser onboarding,
      full release/CI and documentation evidence pass.

### M8 — Application performance monitoring (PLANNED)
- [ ] M8-01: service RED measures/rates use mathematically justified span
      populations and declared sample windows; no rate from raw gauges alone.
- [ ] M8-02: actual trace waterfall latency/error/status and logs-in-context
      agree with known instrumented reference spans and missing parents.
- [ ] M8-03: observed-only dependencies, project isolation, bounded query,
      missing data/truncation, time/cost limits and browser acceptance pass.

### M9 — Host and Kubernetes collection (PLANNED)
- [ ] M9-01: official OTel Collector host/container/K8s receiver configs and
      versioned deployment examples run with least privileges.
- [ ] M9-02: live host and real cluster attributes and receiver/source status
      are verified; historical labels never imply a healthy current host/node.
- [ ] M9-03: host/K8s test environment isolation, credentials, limits,
      startup/recovery, security and operator acceptance pass.

### M10 — Querying, dashboards and telemetry economics (PLANNED)
- [ ] M10-01: defined aggregate, rate and percentile semantics match reference
      data; cardinality, sampling/temporality and empty series are explicit.
- [ ] M10-02: configurable multi-panel dashboards, filters, time windows,
      retention policy, limits, privacy and query budgets are verified.
- [ ] M10-03: scale/performance, tenant isolation, truncation/dependency
      errors, UI and cost measurements are documented.

### M11 — Continuous alerting and SLOs (PLANNED)
- [ ] M11-01: durable scheduled evaluations, retry/restart semantics,
      deduplication and silencing are verified with deterministic clocks.
- [ ] M11-02: delivery history and policy-driven notification outcomes avoid
      duplicates after failures/recovery and respect project boundaries.
- [ ] M11-03: explicit SLO windows, error budgets and no-data semantics are
      validated against reference fixtures; no SLO fabricated from missing data.

### M12 — Browser/mobile telemetry and incidents (PLANNED; scope into slices)
- [ ] M12-01: browser/RUM public-token threat model, CORS, abuse limits,
      rate/retention/privacy controls and safe ingestion are reviewed first.
- [ ] M12-02: real browser error/performance SDK and mobile test coverage
      protect PII, tenant boundaries and public endpoints.
- [ ] M12-03: incident lifecycle/roles and integrations have independent
      test plans, durable histories and real end-to-end browser acceptance.

### Cross-cutting — Production readiness (ongoing, NOT certified)
- [ ] P-01: deployment, backups and actual restore drill, database migration,
      schema compatibility, upgrades and rollbacks are exercised.
- [ ] P-02: secrets, egress/network policy, least privilege, load/cost limits,
      retention/privacy and security review have approved evidence.
- [ ] P-03: Sentrix self-monitoring, failure detection, documented runbooks,
      measured reliability objective and production-like acceptance are in place.

## 8. Acceptance evidence entry — copy per submilestone and test run

```markdown
### <Milestone ID> — <descriptive name>
- Status: NOT RUN | PASS | FAIL | BLOCKED | N/A
- Operator / reviewer / approval: <names or role, no credentials>
- UTC timestamp and timezone: <YYYY-MM-DDTHH:MM:SSZ>
- GitHub baseline / tested commit / pushed commit: <full SHAs>
- Scope and out-of-scope features: <what this run proves / does not prove>
- Test plan case IDs and commands: <exact safe commands>
- Backend / frontend / lint / typecheck / build: <results, warnings>
- CI: <workflow run URL, conclusion and tested SHA>
- Real producer: <framework/Collector version, environment, route, observed signals>
- Evidence IDs: <project UUID, run/trace IDs, window; never raw key>
- Browser evidence: <routes, viewport, screen captures, keyboard/focus, result>
- Security: <separate-user membership, attempted foreign route, HTTP code,
  confirmation no data-plane query; no session cookies>
- Negative/failure/bounds: <invalid auth, 503, truncation, missing data,
  retries, what was/was not simulated>
- Teardown: <temporary credential revoked, temporary resources accounted for>
- Failures/deviations/links: <blockers and owner; do not erase failed runs>
- Final gate decision: ACCEPTED | NOT ACCEPTED | BLOCKED
- Reviewer sign-off and release commit: <recorded only after gates pass>
```

Run per-slice focused checks first, then `./scripts/verify.ps1` on the operator's
Windows/Docker checkout. After a signed-off evidence-only change, commit and push
it; confirm the actual remote SHA before advancing. Never overwrite original
operator results solely to match this master checklist.
