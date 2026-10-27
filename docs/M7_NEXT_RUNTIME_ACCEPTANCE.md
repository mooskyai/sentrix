# Sentrix M7.3.3a — isolated Next.js Node runtime acceptance (candidate)

**Baseline:** `5427d4fa75c865987b0721a4319a263ec46ff972` (M7.3.2 complete and CI successful).  This change implements a **candidate**, not a verified or committed M7.3.3a acceptance. Do not mark it passed until real runtime / persistence / browser / security and CI evidence are recorded.

## Observed operator checkpoint (2026-10-27; release OPEN)

Live Next.js direct export and independently tenant-scoped ClickHouse read-back
**PASSED**, as did owner exact-trace/service API 200 and foreign-user API 404,
308 backend/103 frontend release tests, four Next.js real-process tests,
Next.js build and npm audit (0 vulnerabilities). The operator confirmed the
three browser checks and that the **same** temporary export credential was
revoked afterward and rejected by live OTLP HTTP 401. Local functional and
security acceptance is **COMPLETE**; lockfile/staging review, milestone commit,
push and exact-SHA CI remain **OPEN**.
Record: [M7.3.3a local evidence](M7_3_3A_LOCAL_EVIDENCE_2026_10_27.md).
Instructions below remain useful for independent reproduction and should not
be mistaken for acceptance results on unrelated installations.

## Scope and boundaries

- Pin **Next.js 16.4.3**, React 19.2.0 and the isolated OpenTelemetry dependencies in `integrations/m7-nextjs-node/package.json`. Use Node.js 24 on the operator host. The fixture must have its **own reviewed, committed `package-lock.json`** before pushing. It is initially not included in the patch because package resolution and native Next.js installation cannot be verified in the patch-generation environment.
- Start a real Next.js App Router server, call real Node `GET /api/checkout`, manually create one OpenTelemetry `SERVER` span with the upstream `NodeTracerProvider` and `OTLPTraceExporter`, and export OTLP/HTTP binary protobuf to Sentrix. The Node-only instrumentation hook runs during Next server bootstrap, but the route also initializes a private provider to survive independent runtime module evaluation. It does **not** prove automatic request instrumentation or generic customer-app compatibility.
- Mark resource and span with `sentrix.acceptance.run=<random 32-hex>`, resource `service.name=m7-nextjs-node-runtime`, `deployment.environment.name=integration`, span `m7.next.checkout`, `http.request.method=GET`, `http.route=/api/checkout`, kind=SERVER.
- The parent probe reads a temporary `telemetry:write` project key from **stdin only** and passes it to its dedicated, short-lived child Next process as an in-memory server environment variable. Never put it in `NEXT_PUBLIC_*`, source, CLI arguments, Git, logs, screenshots, or a shell history entry. No browser receives the key. Only loopback or Compose `api` HTTP origins are allowed; remote origins require HTTPS. The application never prints the secret.
- The route waits for a successful upstream SDK exporter callback before returning HTTP 200. **This is only an export acknowledgement, not persistence proof.** The independently authenticated Django/ClickHouse read-back must confirm exactly one stored span in the key-derived project and organization, with strict UTC window, identity and limits.
- Run only on a developer machine. This temporary Next server and probe are not a production deployment, reverse proxy or multi-request stability claim. Browser instrumentation and Edge runtime are expressly out of scope.

## Install and review dependencies (PowerShell)

From repository root:

```powershell
Set-Location "C:\working\Projects\Python\sentrix"
Push-Location .\integrations\m7-nextjs-node
try {
    npm install --package-lock-only --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Next.js lockfile resolution failed" }
    # Review pinned versions and lockfile changes before running npm ci.
    npm ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "Next.js installation failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Next.js build failed" }
    npm test
    if ($LASTEXITCODE -ne 0) { throw "Next.js fake receiver tests failed" }
    npm audit --omit=dev --audit-level=moderate
    if ($LASTEXITCODE -ne 0) { throw "Next.js dependency audit failed" }
} finally { Pop-Location }
```

The `npm test` fake-receiver test actually launches a Next.js server, checks its genuine OTLP protobuf request and exact span/resource attributes, and verifies 401 receiver fail-closed, rejected destinations/CLI secrets and missing stdin. Unlike the Django regression tests, this test requires installed Next.js dependencies. The initial patch has no generated lockfile: **do not commit/CI this fixture without a reviewed lockfile and a successful `npm ci`.** If `npm run build` uses a different Next.js process lifecycle, diagnose before claiming compatibility.

## Live direct export to Sentrix

Ensure the Compose API is running on `http://localhost:8000`, the ClickHouse schema is ready and the target project has a **fresh, private** `telemetry:write` key. Previously disclosed/revoked M7.3.2 keys cannot be reused. From repo root:

```powershell
$token = Read-Host "Temporary Next.js project API key" -MaskInput
try {
    $token | node .\integrations\m7-nextjs-node\probe.mjs --base-url http://localhost:8000
    if ($LASTEXITCODE -ne 0) { throw "Real Next.js SDK export NOT VERIFIED" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

Record the *new* `Run ID`, `Trace ID`, `Time (UTC)` and service from the producer. It must say a real Next.js App Router request exported a span. The server key remains server-side.

## Independent durable read-back

Using the **same active key**, but read it again privately; substitute only nonsecret values printed by the preceding probe:

```powershell
$token = Read-Host "Same temporary project key" -MaskInput
try {
    $token | docker compose exec -T api /opt/venv/bin/python -m scripts.m7_next_readback `
        --run-id "<NEW_RUN_ID>" --trace-id "<NEW_TRACE_ID>" --time "<NEW_UTC_TIME>"
    if ($LASTEXITCODE -ne 0) { throw "Next.js ClickHouse persistence NOT VERIFIED" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

This read-only verifier authenticates the key in PostgreSQL, derives its tenant and checks one exact span from `sentrix_spans`. It queries typed UUID tenant predicates, exact service/env/run ID, plus `LIMIT 2`, eight-second cap and max 250,000 read rows. It rejects wrong tenant, no row, duplicate row, malformed IDs, mismatched route/name/attributes and out-of-window timestamps; errors are sanitized. A 200 without this independent read-back is **not a pass**.

## Remaining acceptance gates (OPEN)

- [ ] Review/commit Next fixture dependency lockfile, `npm ci`, native Next `npm run build` and `npm test`; record Node/Next/OTel versions and zero high/moderate audit findings.
- [ ] Successful direct Next.js server request → upstream real SDK export → independent exact project-scoped ClickHouse span read-back with nonsecret IDs/UTC and service proof.
- [ ] Authenticated member browser Services and Traces, and distinct nonmember browser + direct API 404 checks for the **Next** span; do not reuse Node/Express trace as Next evidence.
- [ ] Key missing/incorrect/expired/revoked HTTP 401 and forbidden-scope 403; no secrets in browser bundles. Revoke temporary key and verify HTTP 401 against the same token after use.
- [ ] Full `scripts/verify.ps1`, Next fixtures, Django focused tests, reviewed staged diff/no secrets, commit/push with exact SHA, green GitHub CI. Optional update to CI Next fixture job only after a reviewed lockfile.
- [ ] Record evidence, reviewer attestation and remaining failures. Do not conflate Next runtime verification with Laravel/Collector acceptance or the global M7.3 milestone.

Note: `Next.js`'s `instrumentation.js` hook is the official server bootstrap location. This candidate explicitly instrumented its own route; it does not certify Next.js automatic spans or an application using Edge functions. See https://nextjs.org/docs/app/guides/instrumentation .
