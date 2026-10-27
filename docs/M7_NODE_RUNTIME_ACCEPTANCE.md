# M7.3.2 — Independent real Node.js/Express runtime candidate

## New primary-project direct SDK proof (2026-10-27)

After recreation of demo organizations/projects, unchanged `probe.cjs` directly
exported SDK OTLP protobuf. Independent ClickHouse read-back verified the real
Node SERVER span (primary project `2017c79d-981f-4f92-9833-303729a4605e`,
run `ffda9340a9954dc4a43157d403dfa018`, trace
`6939aca272bdbaa52a264c630576c0bb`, UTC `2026-10-27T03:29:45.625Z`).
Subsequent owner/nonmember authorization, revoked key 401 and three operator
browser checks passed; full release sign-off requires reviewed commit and CI.
See [current closeout](M7_3_2_FINAL_ACCEPTANCE_2026_10_27.md).

## Actual operator persistence proof (2026-10-26; manual closeout OPEN)

After replacing WSGI `runserver` with Uvicorn ASGI, the original unmodified
`probe.cjs` direct exporter (not the in-memory relay) successfully emitted a
real Express SDK SERVER span. The independent verifier found it in ClickHouse
with project `07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`, run
`ddbaab4290524f2092254fb23ff01613`, trace
`2f06c0b95492feea6379d231993c5b5d`, UTC `2026-10-26T08:25:53.243Z`.
After rebuilding the API the full release gate passed 277 backend and 103
frontend tests, four Node tests and a zero-vulnerability npm audit. This
upgrades the *direct SDK trace persistence* gate to VERIFIED; actual browser,
foreign-user 404, key revocation, cleanup and post-commit CI remain OPEN.
Follow [the operator closeout evidence](M7_NODE_CLOSEOUT_EVIDENCE.md).

## Synthetic demo rows are not M7.3.2 runtime evidence

If the synthetic demo project needs Node-shaped example data, rerun
`manage.py seed_demo --username admin` (full command in `DEMO_SEEDING.md`).
This writes `demo-node-express` metrics/logs/HTTP span through a Python demo
producer, with explicit synthetic marker, not real Node SDK instrumentation.
It never creates `m7-node-express-runtime` or the real SDK's run marker and
cannot be used to satisfy persisted SDK evidence. The operator's exact
`m7-node-express-runtime` read-back still found zero rows. Diagnose the real
export/receiver path separately; never loosen project constraints or time
bounds to make synthetic fixture data pass.

**Implementation candidate, not accepted.** A separate Express HTTP server receives a real
`GET /checkout` request. The Node SDK, started *before Express loads*, manually records a
single `SERVER` span (`m7.node.checkout`), exports OTLP/HTTP **binary protobuf**, and
prints nonsecret run ID, trace ID and UTC timestamp. This does not certify automatic
Express instrumentation, customer's deployed services, continuous connection, metrics,
logs, multi-tenant browser authorization or all of M7.3.

## Node fixture and dependency isolation

Fixture: `integrations/m7-node-express/`. It uses Node >=22 (Node 24 recommended),
Express 5.1.0, NodeSDK/OTLP protobuf exporter 0.223.0 and OpenTelemetry API 1.9.0.
Top-level dependency versions are exact and separate from the Vite application.
**A reviewed npm lockfile is still required before sign-off:** use `npm install
--package-lock-only --ignore-scripts`, examine the resulting `package-lock.json`,
then use `npm ci --ignore-scripts`. Do not commit an unreviewed generated lockfile
or claim fully reproducible transitive resolution before that lock is committed.
No change is made to frontend production dependencies or `backend/uv.lock`.

From **Windows PowerShell** at repository root:

```powershell
Set-Location "C:\working\Projects\Python\sentrix\integrations\m7-node-express"
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
npm ci --ignore-scripts --no-audit --no-fund
npm test
$token = Read-Host "Temporary telemetry:write key" -MaskInput
try {
    $token | node .\probe.cjs --base-url http://localhost:8000
    if ($LASTEXITCODE -ne 0) { throw "Node SDK exporter not accepted" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

`npm test` independently starts a fake OTLP receiver, launches a real Express
subprocess, decodes actual protobuf and asserts the HTTP transport, Bearer
header, resource/run labels, HTTP route/method and server span. It also tests
receiver rejection, unsafe origins, prohibited CLI key and missing stdin key.
This fake endpoint does **not** verify Sentrix persistence or real key usability.
Keep fake credentials in the test, never a real project key in a code file.

**2026-10-25 correction:** The first Windows `npm test` run passed three of four
cases but failed protobuf decoding with `RangeError: index out of range`.
The test's minimal `proto/trace.proto` wrongly declared Span's timestamp
fields 7 and 8 as varint `uint64`. The actual OTLP SDK exports **`fixed64`**
(wire type 1); both fields are now corrected and the real-process test asserts
positive, increasing decoded timestamps. This is a decoder-fixture fix, not
evidence of successful rerun or persisted Sentrix telemetry. Re-run `npm test`
from the Node fixture directory before starting live acceptance. The npm
install also reported **two moderate audit findings**; run `npm audit` and
review the dependency paths before committing the generated lockfile. Do not
blindly run `npm audit fix --force` (it may change pinned compatibility).

## Docker Compose network alternative

Do **not** use Windows-installed native `node_modules` inside a Linux container.
From the fixture directory, use a throwaway Node image on Sentrix's actual
Compose network after `docker compose up -d` (the network is typically
`sentrix_default`; verify it with `docker network ls`). A temporary workdir
inside the container gets Linux dependencies and its own npm lock:

```powershell
$token = Read-Host "Temporary telemetry:write key" -MaskInput
try {
    $token | docker run --rm -i --network sentrix_default `
      --mount "type=bind,source=$((Get-Location).Path),target=/source,readonly" `
      -w /runtime node:24-alpine sh -c `
      'cp -R /source/. /runtime/ && rm -rf node_modules && npm ci --ignore-scripts --no-audit --no-fund && node probe.cjs --base-url http://api:8000'
    if ($LASTEXITCODE -ne 0) { throw "Node container SDK export failed" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

Inside the Node container, `localhost` refers to that container, **not** the
Sentrix API container. `http://api:8000` is allowed only on the trusted same
Compose network; a remote origin must be HTTPS without userinfo, query, path,
or fragment. Do not pass the key in `docker run -e`, command arguments, shell
history, Git, log files, browser JavaScript or screenshots.

## Independent authenticated ClickHouse read-back

Record **Run ID**, **Trace ID**, **Time (UTC)** output by the *real Sentrix*
producer. Return to the repository root and provide the same active, temporary
project key on stdin to the Django API container (fill only nonsecret strings):

```powershell
Set-Location "C:\working\Projects\Python\sentrix"
$token = Read-Host "Same temporary project's key" -MaskInput
try {
    $token | docker compose exec -T api /opt/venv/bin/python -m scripts.m7_node_readback `
      --run-id "<RUN_ID>" --trace-id "<TRACE_ID>" --time "<UTC_TIMESTAMP>"
    if ($LASTEXITCODE -ne 0) { throw "Express persistence NOT VERIFIED" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

The verifier uses Django/PostgreSQL to validate the `telemetry:write` scope
and derive the organization's and project's UUIDs. The `sentrix_spans` query
uses typed UUIDs, a 10-minute UTC window, exact service/environment/run ID,
`LIMIT 2`, an eight-second execution cap and a 250,000-row scan ceiling.
Exactly one stored span must match the producer trace ID, nonzero span ID,
`SERVER` kind, `m7.node.checkout` operation, `GET` and `/checkout`, both run
markers, resource labels and ordered timestamps. Only known ClickHouse
`DateTime64(9,'UTC')` naive values are normalized to UTC. Empty, duplicate,
malformed, mismatched, wrongly scoped and dependency-failed reads do not pass.

An OTLP HTTP 200 or a fake receiver success is **not** proof of persistence.
The read-back is independent and read-only. It is not an authenticated browser
foreign-user check, and does not assert a constantly connected exporter.

## Operator acceptance record (NOT YET RECORDED)

Record commit SHA, exact dependency lock SHA/versions, API project ID,
nonsecret run/trace IDs, UTC time, network category, Node test result, the
full `scripts/verify.ps1` release gate, persisted read-back result, real
Services/Traces UI screenshots without secrets, foreign-user 404, invalid/
expired/revoked key behavior, credential revocation, CI run and reviewer.
Do not mark M7.3.2, M7.3, M7.4, or prior M6/M7 manual gates accepted without
these independent results. Do not begin M7.3.3 until accepted/pushed unless
explicitly directed.
