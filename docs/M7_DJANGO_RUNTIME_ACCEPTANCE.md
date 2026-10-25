# M7.3.1 — Isolated Django/Python runtime acceptance

**Implementation candidate.** This runbook exercises a **real Django WSGI application** in
an independent process, sends one genuine HTTP request to its view, records a manually
instrumented server span using the upstream OpenTelemetry Python SDK, and posts OTLP/HTTP
protobuf to Sentrix. A second command verifies the **actual stored span** through
a temporary project's authenticated tenancy and bounded ClickHouse read-back.

This example deliberately uses **manual server-span instrumentation**, not Django
zero-code/automatic instrumentation. It does **not** certify an arbitrary existing
Django deployment, middleware coverage, Collector pipelines, multi-signal output,
production security, retries, or browser acceptance. Those are distinct M7.3 gates.

## Requirements

- Healthy `docker compose up -d` including `api`, PostgreSQL and ClickHouse; run
  `./scripts/verify.ps1` and record the results before closeout.
- A temporary `telemetry:write` project API key from **Settings** for the exact
  destination project. The raw key is never supplied as an argument, URL, or file.
- Use `http://api:8000` from **inside the API container**; the producer rejects
  nonlocal cleartext HTTP, URL credentials and URL query tokens. For a remote
  receiver, use a reachable HTTPS origin.
- SDK and exporter are in the backend's existing development dependency group:
  `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`. The smoke code does
  not change the app's production packages or `uv.lock`.

## Run the Django WSGI producer

From PowerShell in `C:\working\Projects\Python\sentrix`:

```powershell
$token = Read-Host "Temporary Sentrix project key" -MaskInput
try {
    $token | docker compose exec -T api /opt/venv/bin/python -m scripts.m7_django_runtime --base-url http://api:8000
    if ($LASTEXITCODE -ne 0) { throw "M7 Django SDK export failed" }
} finally {
    Remove-Variable token -ErrorAction SilentlyContinue
}
```

Capture the printed **Run ID**, **Trace ID** and **Time (UTC)** without the
credential. One isolated `/checkout/` request must succeed, and the trace exporter
must return success. This is **not** storage evidence.

## Independently verify ClickHouse persistence

Use the same still-active project key. Replace the example placeholders below
with the **printed values** from the producer (no quotes around placeholder
labels in the command itself; PowerShell strings for actual values are fine).

```powershell
$token = Read-Host "Same project's temporary key" -MaskInput
try {
    $token | docker compose exec -T api /opt/venv/bin/python -m scripts.m7_django_readback `
        --run-id "<RUN_ID>" --trace-id "<TRACE_ID>" --time "<UTC_TIMESTAMP>"
    if ($LASTEXITCODE -ne 0) { throw "M7 Django persistence verification failed" }
} finally {
    Remove-Variable token -ErrorAction SilentlyContinue
}
```

The verifier authenticates the key through Django/PostgreSQL (not supplied tenant
UUIDs), requires `telemetry:write`, and reads from `sentrix_spans` with **typed
organization/project parameters**, exact service `m7-django-runtime`, environment
`integration`, the unique run marker and a UTC ten-minute window. It requires
exactly one `m7.django.checkout` server span, the producer's trace ID, a nonzero
span ID and ordered timestamps. More/missing/foreign results fail closed. Queries
use a 2-row cap and ClickHouse read/time budgets. Neither tool prints secrets.

## UTC timestamp read-back compatibility

ClickHouse Connect returns UTC `DateTime64(9, 'UTC')` columns as **naive UTC**
Python `datetime` objects by default. The read-back verifier explicitly
attaches UTC to those two schema-defined columns before checking the exact
five-minute-before/five-minute-after evidence window. It still rejects
out-of-window, reversed, malformed, missing, repeated and cross-project rows.

An operator run on 2026-10-25 reported SDK OTLP export accepted with run ID
`3ac7ac6765ea487cbd5de61b32bb1090`, trace ID
`06b5945cf479625c5a7a051bb748ca3a` and observed UTC time
`2026-10-25T08:18:57.946820+00:00`. The original read-back found a matching
row but **rejected its timestamp**. After applying the UTC correction and
passing the full release gate, the operator reran read-back for this exact
run and received `Django runtime persistence VERIFIED: real Django WSGI server
span in key's project.` The verifier reported project
`07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`. **This run's SDK export and
project-scoped ClickHouse persistence are verified.**

The operator's corrected full gate passed 250 backend tests, 102 frontend
tests, Ruff lint/format, strict mypy, Django and ClickHouse checks, ESLint,
TypeScript and the production build. These results do not prove browser UX,
foreign-user 404, credential revocation or other runtimes.

## Negative paths and acceptance record

- Wrong/revoked key, remote insecure origin and OTLP refusal: failure must not
  produce a successful persistence claim. **Do not record raw keys or exporter headers.**
- Wrong run ID or trace ID and key from an unrelated project: no verified span.
- Separate signed-in user without project membership: project telemetry-read
  endpoint returns 404 before ClickHouse (not proven by key-derived read-back).
- Browser Services and Traces: find the same service/environment and trace ID in
  a window containing its timestamp; verify mobile and keyboard behavior.
- Revoke the temporary key and record credential cleanup.

Evidence fields: tested commit SHA, date/time in UTC, SDK/Django versions,
run ID, trace ID, project ID, exporter origin category (not secret-bearing URL),
producer result, read-back result, foreign-user/browser results, CI URL, key
revocation and unresolved exceptions. The Django SDK and project-scoped persistence run are **VERIFIED**; the
remaining manual security/browser/credential-cleanup and whole-milestone
acceptance items are **NOT RUN / NOT RECORDED**. M6 manual acceptance and
M7.1/M7.2 browser acceptance stay independently open.
