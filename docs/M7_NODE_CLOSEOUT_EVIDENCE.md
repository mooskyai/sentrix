# M7.3.2 — Real Node/Express SDK closeout evidence (2026-10-26)

## 2026-10-27 follow-up: local acceptance complete, CI still open

The following 2026-10-26 record is historical. The current primary demo
project replaces the old deleted project; direct SDK, foreign-user 404,
revoked-key 401 and all three operator browser checks now passed. Latest
release gate: 290 backend, 103 frontend, strict mypy 130 sources, build/schema.
See the sanitized [current evidence](M7_3_2_FINAL_ACCEPTANCE_2026_10_27.md).
M7.3.2 is **not fully released** until reviewed commit, push and exact-SHA CI.

**Status: direct SDK trace persistence VERIFIED; M7.3.2 full acceptance OPEN.** This is a
sanitized operator-evidence record, not a certificate of general auto-instrumentation,
production readiness or the M6/M7.1/M7.2 manual gates. Do not mark the full milestone
complete or move to M7.3.3 until the remaining independent checks and a clean pushed CI
commit are recorded.

## Verified runtime evidence

| Requirement | Actual operator evidence |
| --- | --- |
| SDK process | Real Express HTTP request; manually instrumented upstream Node OpenTelemetry SDK `SERVER` span; OTLP/HTTP binary protobuf |
| Failure reproduced | Before ASGI, direct SDK export HTTP 200 with zero persisted Node rows. Exact trace scans and project-scoped seven-day read returned zero; prior Django span existed |
| Transport diagnosis | Direct SDK used `Transfer-Encoding: chunked`, lacked `Content-Length`, and emitted 1,041 nonempty protobuf bytes (local fake-receiver inspection) |
| Correction | Local Compose API now serves Django `config.asgi:application` with Uvicorn instead of development WSGI `runserver`; malformed empty chunked input fails closed with HTTP 400 |
| ASGI startup | Uvicorn startup complete at `http://0.0.0.0:8000`; GET `/v1/traces` returns expected HTTP 405 |
| Direct SDK export | `probe.cjs` → actual local Sentrix receiver, unaltered SDK transport, `m7-node-express-runtime` / `integration`, 2026-10-26T08:25:53.243Z |
| Independent read-back | `Node Express persistence VERIFIED: real Express server span in key's project.` (not HTTP 200 alone) |
| Project ID | `07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d` |
| Run ID | `ddbaab4290524f2092254fb23ff01613` |
| Trace ID | `2f06c0b95492feea6379d231993c5b5d` |
| Diagnostic relay (separate earlier proof) | Run `41e07e34adc641ce822d39649914ccac`, trace `a42429c7f2c9d8209ee9919057646e76` stored from real SDK bytes forwarded by relay |
| Rebuilt backend | Python 3.14.9, Django 6.1.2; full `scripts/verify.ps1` reported **277 backend passed, 1 warning; 103 frontend passed**; Ruff lint/format and strict mypy for 124 files passed; schemas/build passed |
| Upstream fixture | `npm test` **4 passed**; `npm audit --omit=dev --audit-level=moderate` **0 vulnerabilities** |
| Synthetic fixture | Synthetic `demo-node-express` was stored separately: two request + two duration points, one log, one marked HTTP SERVER span; zero secondary-project samples |
| Git baseline | Operator confirmed `main` at `2f6b46c0daf7119dddf66c416fc1c992f943972e` before M7.3.2 patches; changes are uncommitted at time of evidence |

Only the actual direct SDK trace/read-back provides direct-runtime acceptance. Synthetic
records, isolated relay success, and tests must not substitute for it.

## Remaining operator acceptance (OPEN)

1. **Real browser**: Sign in to Sentrix at `http://localhost:5173` as a project
   member; select the primary Online Store project, then inspect **Services** for
   `m7-node-express-runtime` / `integration` and **Traces** for the exact trace ID.
   Use an absolute time window including `2026-10-26T08:25:53.243Z` (within the
   API's seven-day maximum), not a later default one-hour window. Record whether
   span name `m7.node.checkout`, kind SERVER and exact run marker are visible.
   Capture a sanitized screenshot or a written observation; no key/cookies.
2. **Independent-user non-disclosure**: Create or use a *different active user*
   without project membership. Run the read-only authenticated API smoke below,
   which expects owner HTTP 200 with exactly the persisted Node span, and foreign
   HTTP 404 for both trace and catalog. This uses in-process DRF authentication,
   so a separate real browser login/session still needs manual confirmation.
3. **Credential lifecycle**: Only after all positive key-dependent read-back is
   complete, revoke the *temporary project API key* using owner-authorized
   Settings → Project API keys. Confirm that the **same revoked key** is rejected
   with HTTP 401 by the actual OTLP endpoint. Do not commit or print the key;
   do not issue further acceptance writes with that key.
4. **Final gate and CI**: Record test SHA, `git diff --check`, staged path review
   including `integrations/m7-node-express/package-lock.json`, complete release
   gate after any edits, commit/push, the exact SHA's CI URL/result, and final
   `main...origin/main` alignment. Exclude local scratch scripts, raw secrets,
   build artifacts, `node_modules`, `.env` and logs.

## Read-only owner/foreign-user API smoke

Run from the repository root after a second existing *active* user without
membership is available. Substitute its username; do not use the `admin` account
or a second project belonging to the same user. No project API key is required.
The script does not create, modify or remove users or telemetry.

```powershell
Set-Location 'C:\working\Projects\Python\sentrix'

docker compose exec -T api /opt/venv/bin/python -m scripts.m7_node_auth_smoke `
  --owner-username admin `
  --foreign-username '<REAL_FOREIGN_USERNAME>' `
  --project-id '07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d' `
  --trace-id '2f06c0b95492feea6379d231993c5b5d' `
  --run-id 'ddbaab4290524f2092254fb23ff01613' `
  --time '2026-10-26T08:25:53.243Z'

if ($LASTEXITCODE -ne 0) { throw 'M7.3.2 authenticated API isolation smoke failed.' }
```

Positive success prints owner observations and both foreign HTTP 404s. A missing
foreign user, foreign account with membership, empty trace, dependency failure,
or non-404 is a **failed or incomplete** gate. This does not impersonate a real
browser login or prove behavior outside this exact tested project.

## Revoked-key HTTP check — operator action

After revoking the temporary key in project Settings, use that *same value*
from a masked PowerShell prompt. This sends an **empty valid protobuf request**
with no span records to the actual Compose-network Uvicorn `/v1/traces`
endpoint; a still-valid key can be tested without writing any telemetry. The
probe passes only when the HTTP response is **401**, not on an unrelated 4xx,
network outage, or timeout. A 401 by itself cannot prove revocation of a
*particular* key unless the operator confirms it was the same previously
active value. No raw key appears in arguments, URLs, source, or output.

```powershell
$token = Read-Host 'Same previously revoked project API key' -MaskInput
try {
  if ([string]::IsNullOrWhiteSpace($token)) { throw 'Missing key.' }
  $token | docker compose exec -T api /opt/venv/bin/python `
    -m scripts.m7_node_revoked_key_probe
  if ($LASTEXITCODE -ne 0) { throw 'Revoked-key HTTP 401 not verified.' }
} finally {
  Remove-Variable token -ErrorAction SilentlyContinue
}
```

Record actual browser, 404 and HTTP 401 observations *only after they happen*.
`M7.3.2` remains OPEN until those results, reviewer approval and post-push CI
are recorded. Earlier milestone manual acceptance remains independently OPEN.
