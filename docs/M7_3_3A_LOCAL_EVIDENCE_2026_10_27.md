# Sentrix M7.3.3a — Next.js local acceptance evidence (2026-10-27)

**State:** M7.3.3a **local functional and security acceptance COMPLETE**.
Real Next.js App Router SDK ingestion, independent ClickHouse persistence,
owner/nonmember API controls, three browser checks and same-credential
revocation were confirmed on 2026-10-27. **Release status: PENDING** reviewed
lockfile/staged changes, final commit/push and successful new exact-SHA CI. This does not certify automatic
Next.js/Edge/browser instrumentation, Laravel/PHP, or the Collector.

## Base and verified runtime

- GitHub baseline and clean working tree prior to the candidate patch:
  `5427d4fa75c865987b0721a4319a263ec46ff972`, `main`.
  Prior M7.3.2 CI: [workflow 40451690954](https://github.com/mooskyai/sentrix/actions/runs/40451690954), success.
- Next.js `16.4.3` isolated App Router fixture; Node.js host runtime;
  manually instrumented `SERVER` span, not automatic tracing.
- `npm install --package-lock-only` and `npm ci` succeeded. `npm run build`
  succeeded including TypeScript and the dynamic `/api/checkout` route.
  `npm test`: **4 passed** (real Next.js to fake OTLP protobuf receiver,
  401 negative case, prohibited origins/CLI secrets, missing stdin secret).
  `npm audit --omit=dev --audit-level=moderate`: **0 vulnerabilities**.
  The generated `integrations/m7-nextjs-node/package-lock.json` still needs
  an explicit staged review and must be included in the commit.
- Real direct HTTP request: `GET /api/checkout`, Next.js Node runtime;
  upstream OTel SDK protobuf export accepted by Sentrix. The independent
  `scripts.m7_next_readback` CLI subsequently verified the one real stored
  server span in the **key-authenticated project's** ClickHouse rows.

| Field | Observed nonsecret value |
| --- | --- |
| Project ID | `2017c79d-981f-4f92-9833-303729a4605e` |
| Service | `m7-nextjs-node-runtime` |
| Environment | `integration` |
| Span operation | `m7.next.checkout` (`SERVER`, `GET /api/checkout`) |
| Run ID | `49a30251d0c749ceb75cd56b9e6406ce` |
| Trace ID | `406fa3db23e9f4c8c98e975424a6179d` |
| Timestamp (UTC) | `2026-10-27T06:17:16.097Z` |
| Persistence | `Next.js persistence VERIFIED: real App Router SERVER span in key's project.` |

This is a real SDK producer, not the 365-day synthetic dataset or the earlier
M7.3.2 Express producer. OTLP HTTP 200 alone would not meet this gate.

## Security — observed and operator-attested

- **PASS (in-process Django/DRF API):** existing authorized user `admin` got
  HTTP 200 and exactly one matching Next.js SERVER span plus the matching
  `m7-nextjs-node-runtime` Services catalog identity; separate user
  `m732-nonmember` without project membership got HTTP 404 from both APIs.
  The logged `Not Found` messages are the expected denial responses.
- **PASS (live OTLP negative test):** `scripts.m7_node_revoked_key_probe`
  reported HTTP **401** for the privately supplied revoked credential.
  That script checks the shared `/v1/traces` endpoint, not a Node-only route.
- **PASS (credential lineage; operator attestation, 2026-10-27):** the user
  explicitly confirmed that the credential rejected with HTTP 401 was the
  **same temporary key used for the successful Next.js export**, subsequently
  revoked. The output alone established a rejected key; identity continuity
  is separately based on this attestation. Never record or commit the secret.
  Review whether any other temporary/exposed keys still need revocation.
- **PASS (real browser; operator attestation, 2026-10-27):** `admin` saw
  `m7-nextjs-node-runtime` / `integration` in Services and inspected the exact
  `406fa3db23e9f4c8c98e975424a6179d` `m7.next.checkout` span within a
  UTC window containing 06:17:16.097. In an independent browser session,
  `m732-nonmember` could not see the project or access its deep link. These
  are operator-reported results, not independently captured screenshots.

## Complete local automated gate (2026-10-27)

- Focused `apps/telemetry/tests/test_m7_next_runtime.py`: **18 passed**.
- `./scripts/verify.ps1`: **308 backend pytest passed**, one warning; **103
  frontend Vitest passed** across 20 files; Ruff check and format, mypy **132
  source files** (no issues), Django checks, migrations, ClickHouse schema
  validation, frontend lint/typecheck and production build all passed.
- This checkpoint occurred before the evidence-only documentation changes;
  no new backend/frontend implementation is introduced by the evidence patch.

## Remaining release checklist

- [x] Isolated Next.js production build, real fake-receiver and adverse tests,
      npm audit.
- [x] Direct SDK export + independent exact key-derived ClickHouse read-back.
- [x] Authorized owner API + separate nonmember 404 isolation for exact Next trace.
- [x] Live revoked-credential OTLP HTTP 401 rejection (supplied key).
- [x] Full local backend/frontend release gate.
- [x] Operator confirmed the **same temporary credential** was revoked after export.
- [x] Operator confirmed three distinct browser acceptance checks.
- [ ] Review and stage npm lockfile, exclude `.next`, `node_modules`, `.env*`,
      local credentials, logs, and unrelated generated files.
- [x] Apply initial documentation evidence patch and pass `git diff --check`.
- [ ] Recheck `origin/main` vs baseline; run any final checks after material edits;
      inspect staged diff and scan for secret material.
- [ ] Commit/push the completed slice; verify exact pushed SHA and passing
      GitHub Actions workflow. Record commit SHA and CI run URL externally to
      avoid creating an evidence commit that changes its own SHA.

Do not claim the separate Laravel/PHP, OpenTelemetry Collector, automatic
instrumentation, M7.4, or production hardening milestones as completed.

## Final release record (record externally after push)

- Base commit: `5427d4fa75c865987b0721a4319a263ec46ff972`
- New M7.3.3a commit SHA: **PENDING**
- Exact-SHA Actions run URL and conclusion (backend/frontend/Next.js jobs): **PENDING**
- Final local tree/staging review: **PENDING**
- Reviewer/maintainer sign-off: **PENDING**

Do not amend a completed release commit simply to insert its own SHA; capture
post-push CI evidence in the GitHub release/issue/PR record instead.
