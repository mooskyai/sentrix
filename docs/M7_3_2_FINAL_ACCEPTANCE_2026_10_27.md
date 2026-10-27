# Sentrix M7.3.2 — final operator acceptance evidence (2026-10-27)

**Milestone stage:** local functional/security acceptance complete, based on recorded
command output and the operator's explicit confirmation of three browser checks.
**Release status: NOT CLOSED until the final documentation commit is pushed and
GitHub Actions passes for that exact commit SHA.** This record does not assert
production readiness, acceptance of other V1 milestones, or verification of
other runtimes.

## Scope and repository baseline

- Repository: `mooskyai/sentrix`, branch `main`.
- On 2026-10-27 the GitHub `main` comparison against
  `2f6b46c0daf7119dddf66c416fc1c992f943972e` was **identical** (0 commits
  ahead/behind). Operator must independently confirm local `HEAD` and
  `origin/main` still match after `git fetch` and before committing.
- Implementation: real Node.js/Express OpenTelemetry HTTP/protobuf export using
  the unmodified `integrations/m7-node-express/probe.cjs` direct transport; ASGI
  Uvicorn receiver replaced the WSGI development server to handle chunked
  transfer framing with absent `Content-Length`. Real observations are separate
  from synthetic demo/history telemetry.

## Real direct SDK proof (recreated primary project)

| Field | Observed evidence |
| --- | --- |
| Project | `2017c79d-981f-4f92-9833-303729a4605e` (Online Store, primary) |
| Service/environment | `m7-node-express-runtime` / `integration` |
| Direct exporter | `node integrations/m7-node-express/probe.cjs --base-url http://localhost:8000` |
| Run ID | `ffda9340a9954dc4a43157d403dfa018` |
| Trace ID | `6939aca272bdbaa52a264c630576c0bb` |
| UTC event timestamp | `2026-10-27T03:29:45.625Z` |
| Wire result | HTTP 200, SDK export accepted (not sufficient by itself) |
| Durable proof | `scripts.m7_node_readback` independently returned `Node Express persistence VERIFIED: real Express server span in key's project.` |
| Diagnostic relay (supplemental) | Run `2e0ff08dfadc4d0297206c5bc59d7509`, trace `01d078f79b5554bc1f97270ad49586a0`, UTC `2026-10-27T03:28:27.202Z`; independently read back after forwarding actual SDK bytes |

**Old/deleted project evidence is superseded:** the earlier 2026-10-26 IDs
(`07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d` and its associated trace) remain in
historical runbooks for the initial receiver diagnosis, but **must not** be
used for current project security or browser closeout.

## Authentication and tenant isolation proof

The operator ran:

```powershell
docker compose exec -T api /opt/venv/bin/python -m scripts.m7_node_auth_smoke `
    --owner-username admin `
    --foreign-username m732-nonmember `
    --project-id 2017c79d-981f-4f92-9833-303729a4605e `
    --trace-id 6939aca272bdbaa52a264c630576c0bb `
    --run-id ffda9340a9954dc4a43157d403dfa018 `
    --time 2026-10-27T03:29:45.625Z
```

Actual result: owner authenticated API reads found the exact persisted Node
span and service; `m732-nonmember` received **HTTP 404** for both the project
trace endpoint and Services catalog. The logged `Not Found` lines are the
expected access-denial responses. This is an in-process Django/DRF smoke,
separate from browser sign-in.

The operator then explicitly confirmed **all three manual browser checks**:

- [x] Signed-in `admin` saw the expected real `m7-node-express-runtime` /
  `integration` identity in Services and the direct trace using a matching
  UTC window.
- [x] Independently signed-in `m732-nonmember` could not access the Online Store
  organization/project.
- [x] The nonmember's attempted project deep link did not expose the project.

These browser outcomes are **operator attestations**, not captured screenshots
or independent automation. Never record browser credentials or session cookies.

## API-key revocation and handling

Two plaintext project keys were exposed in conversation and must never be
copied into this repository, logs, screenshots, CI output or documentation.
Only nonsecret **public prefixes** are recorded here:

- `ba7a4536ae7d`: database query showed `revoked=True`, `expired=False`.
- `a8719883c247`: initially active; later database showed `revoked=True`,
  `expired=False`, and its **live OTLP HTTP request returned 401**, with
  explicit result `PASS: revoked key rejected with HTTP 401.`

An HTTP 200 observed before the second key was revoked was not a security
failure. The earlier `m7_node_revoked_key_probe` output alone did not prove
acceptance; the subsequent DB-state + live HTTP-status diagnostic did.
Review the project's remaining API-key inventory before release and revoke any
other temporary/exposed credentials. Never print or commit plaintext tokens.

## Historical dataset (separate, synthetic-only)

`manage.py seed_demo_year --username admin --days 365 --create-nonmember`
succeeded for two demo projects. Both reported **365 days written** and
**159 historical OTLP requests per project**. Secondary project:
`30a919da-f0f6-43f6-8fc7-bef706ae7baa`.
The seed also created/reused the `m732-nonmember` account with zero memberships.
History uses synthetic markers; these rows are **not** evidence of real SDK
persistence. Browser query choices remain capped by the implemented seven-day
range. The `seed_demo` wrapper appends recent data on each rerun.

## Automated release gate evidence

The operator's `./scripts/verify.ps1` result on Python **3.14.10** and Django
**6.1.2** (2026-10-27), **after the one-year seed/mypy corrections**:

- **290 backend pytest tests passed**, 1 warning.
- **103 frontend Vitest tests passed**, 20 test files; ESLint, TypeScript and
  production Vite build passed.
- Ruff lint and format passed; strict mypy: **130 source files**, zero issues.
- Django checks, migration detection and ClickHouse schema validation passed.
- Final output: `All release-gate commands passed.`

Earlier upstream Node fixture verification was **4 tests passed**, and
`npm audit --omit=dev --audit-level=moderate` reported **0 vulnerabilities**.
Those results must be rerun or reconfirmed before final commit if Node files
or the lockfile have changed since that evidence.

## Release / CI gate (OPEN until recorded)

- [ ] `git fetch origin main`, then local `HEAD == origin/main ==`
  `2f6b46c0daf7119dddf66c416fc1c992f943972e` prior to commit; no remote
  divergence, or stop and reconcile explicitly.
- [ ] Review all tracked/untracked file changes; exclude local scratch files,
  generated assets, `.env`, API-key plaintext, database dumps, caches,
  `node_modules`, screenshots and unrelated edits; inspect `package-lock.json`.
- [ ] Apply the evidence patch; check `git diff --check`, Ruff, strict mypy,
  final `scripts/verify.ps1`, Node tests and npm audit as applicable.
- [ ] Review `git diff --cached --name-status` and `git diff --cached --check`;
  scan staged content for `sentrix_pk_<public-prefix>_<secret>` shaped strings.
- [ ] Commit approved M7.3.2 implementation/tests/docs (including this file).
- [ ] Push to `origin/main` only if that is the authorized release workflow.
- [ ] Observe **successful GitHub Actions checks for the exact pushed commit**;
  a green check for an earlier SHA is not sufficient.
- [ ] Record committed SHA, workflow URL/result and final branch alignment
  in the external GitHub release/issue/PR acceptance record, then obtain sign-off.

A tracked commit cannot record its own final SHA before it exists. Record
post-push SHA and Actions URLs externally; amending or committing this document
again creates a different SHA and requires fresh exact-SHA CI verification.

**Commit SHA:** `PENDING` (record externally after push)

**GitHub Actions run URL:** `PENDING`

**Exact-SHA CI conclusion:** `PENDING`

**Reviewer / release sign-off:** `PENDING`

Do not mark M7.3.2 fully released or advance to M7.3.3 until these remaining
items are complete. Outstanding manual acceptance for M6, M7.1, M7.2, and
other frameworks remains independent from this Node.js milestone.
