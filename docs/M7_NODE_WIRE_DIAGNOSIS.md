# M7.3.2 — real Express OTLP persistence boundary diagnostic

**2026-10-26 operator update:** Relay path succeeded with real SDK span and
independent ClickHouse proof (`41e07e34adc641ce822d39649914ccac` /
`a42429c7f2c9d8209ee9919057646e76`). The unmodified direct exporter still
failed persisted read-back (`3abe18c8d7594ac6b478ef66e5011b75` /
`34180aba65cf5ccd47973c2c964d0168`). See
`M7_NODE_HTTP_FRAMING.md` for the proposed ASGI correction and next live gate.
Do not treat the following original diagnostic narrative as the latest status.

**Diagnostic candidate; live Node SDK persistence is NOT accepted.** Do not
replace `m7-node-express-runtime` with `demo-node-express` or count the synthetic
seeder as external SDK evidence. The operator previously observed real Node
OTLP HTTP 200, followed by zero ClickHouse rows for two run/trace IDs, even
without a time filter. The same authenticated project retained the verified
Django SDK span. Synthetic Node-shaped data is separately verified.

This diagnostic uses a **loopback-only, in-memory relay** to inspect the *same*
binary OTLP protobuf body produced by a real Express HTTP request. It forwards
those bytes unchanged to the specified Sentrix `/v1/traces` receiver with the
same `telemetry:write` key. The forwarded real SDK request may create one legitimate span in the target
project; it is not a read-only request. It then sends the buffered OTLP body over
stdin to Django's production decoder and ClickHouse **row normalizer**; this
stage writes nothing. Finally, it supplies the same project key on stdin to
the existing independent, tenant-scoped ClickHouse read-back command.

## Run (PowerShell 7; Docker Compose API and Node dependencies running)

From the canonical repository root, after checking `git status -sb` and
`git diff --check`, run the already-installed Node fixture (Node >=22):

```powershell
Set-Location 'C:\working\Projects\Python\sentrix'
$token = Read-Host 'Same temporary telemetry:write project key' -MaskInput
try {
    $token | node .\integrations\m7-node-express\diagnose.cjs --base-url http://localhost:8000
    if ($LASTEXITCODE -ne 0) { throw 'Real Node SDK persistence diagnostic failed.' }
} finally {
    Remove-Variable token -ErrorAction SilentlyContinue
}
```

The node fixture must have a reviewed `package-lock.json` and
`npm ci --ignore-scripts` already completed; do not re-install dependencies
unnecessarily. The diagnostic requires the `docker` command on the host and
uses `docker compose exec -T api` within the canonical repository directory.
Never provide an API key in arguments, Git, screenshots, debug logs or files.
It does not store wire payloads or tokens. It processes at most one SDK POST,
with a 2 MiB request and 64 KiB response bound; the relay listens only on
`127.0.0.1`. Only local loopback/trusted Compose HTTP and clean remote HTTPS
origins are permitted by the existing `probe.cjs` URL policy.

## Interpret each stage

- **SDK wire stage fails**: Node is not exporting exactly one SERVER span with
  the run/trace marker, or the HTTP receiver rejected the request. Check the
  SDK installation, origin and HTTP status. Do not claim persistence.
- **SDK wire passes but Django canonical decode fails**: the Python OTLP decoder
  or the span normalizer is incompatible with the actual Node SDK binary.
  Correct the confirmed protobuf/normalization mismatch with a test using the
  same SDK wire shape; do not weaken project or timestamp predicates.
- **SDK and Django wire stages pass but read-back fails**: the SDK generated a
  real span, the *same* bytes were forwarded and the production Python parser
  normalizes them to one row, but persistence is not verified. Examine Django
  receiver routing, resource-group/leaf-record handling, sink insertion,
  ClickHouse target/retention and the authenticated project UUID before any
  patch. HTTP 200 alone is not evidence of a durable row.
- **All three pass**: the real SDK's exact project/run/trace has independent
  persistence evidence. Browser, separate foreign-session 404, revoked-key,
  teardown, CI and reviewer approval remain outstanding.

The offline wire inspector uses fake UUIDs **only in memory** to run the existing
row normalizer; it never writes to ClickHouse and never grants authorization.
The actual read-back derives both tenant UUIDs from the scoped PostgreSQL key.
This diagnostic adds no new receiver endpoint, schema or browser key handling.

Operator evidence in this file is intentionally **pending** until the script is
run in the actual Windows/Docker environment. Keep M7.3.2 open and uncommitted
until root cause correction, live read-back, tests and remaining gates pass.
