# Sentrix M6 — Live OTLP operator evidence producer

## M6.5 persisted read-back — independent verification step

After a successful producer run, **use a temporary project key from the same
project** (the key may be a new one if the original was revoked). Run this in
PowerShell 7 from the repository root. Use the *actual* producer identifiers;
never put the secret in the command, console transcript, URL or Git repository.

```powershell
Set-Location "C:\working\Projects\Python\sentrix"
$token = Read-Host "Temporary Sentrix project key" -MaskInput
try {
  $token | docker compose exec -T api /opt/venv/bin/python -m scripts.m6_readback `
    --run-id 319b34b2346645fe8729b5518ca8a236 `
    --trace-id 29b8393d3bef43d191ebc371b0113e26 `
    --time "2026-10-24T17:11:41.422946+00:00"
  if ($LASTEXITCODE -ne 0) { throw "M6 persisted read-back failed" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

The verifier is launched with `python -m` from `/app`, so the Django `config`
package resolves correctly; direct file execution is also supported.

The IDs/time above identify one earlier controlled run; replace them with a
fresh producer's output where possible. The verifier opens Django/PostgreSQL
to authenticate the project key, then queries ClickHouse (no new OTLP request).
It checks exactly three rows per signal, service/environment, resource labels,
trace correlation and two span-parent edges. It is bounded to five minutes
before and after the supplied UTC timestamp and 100 rows per signal; failed
or incomplete evidence results in a nonzero exit without a fabricated pass.

This read-back proves neither the separate-user 404/authorization behavior of
session-read APIs nor what a human actually saw in the browser. It is not a
real instrumented external framework, Kubernetes inventory, collector health,
reliable retry proof, or teardown verification. Record those separately in
M6.2–M6.4 acceptance docs and the M6.5 closeout decision. Revoke test keys.


**State: operator tool, not acceptance.** The test utility generates trace-correlated
metrics, logs and spans using the real OTLP/HTTP binary-protobuf endpoint. This
is an independent Python producer process, not a certified framework integration
or proof of a production workload. Its names and Kubernetes resource attributes
are **synthetic**: receiving `k8s.*` labels does not establish an actual cluster.
The tool is append-only and never creates or revokes keys or deletes telemetry.

## Requirements

- Run Docker Compose (`docker compose up -d`) with healthy API and ClickHouse.
- Log into Sentrix and create a **temporary** `telemetry:write` project key in
  that exact project's Settings. Never paste the key into console transcripts,
  chat, source control, URLs, CLI flags, or browser JavaScript.
- Prefer a separate Python 3.14 process on the Windows host to verify the host
  → API network path. From the repository root, use **PowerShell 7**:

```powershell
$token = Read-Host "Temporary Sentrix project key" -MaskInput
Push-Location .\backend
try {
  $token | uv run python scripts/m6_acceptance_smoke.py --base-url http://localhost:8000
  if ($LASTEXITCODE -ne 0) { throw "OTLP smoke failed" }
} finally {
  Remove-Variable token -ErrorAction SilentlyContinue
  Pop-Location
}
```

If `uv` is unavailable on the host, use the already installed Python packages
inside Compose instead (this checks the HTTP ingestion contract but **not** a
separate host-network path):

```powershell
$token = Read-Host "Temporary Sentrix project key" -MaskInput
try {
  $token | docker compose exec -T api /opt/venv/bin/python scripts/m6_acceptance_smoke.py
  if ($LASTEXITCODE -ne 0) { throw "OTLP smoke failed" }
} finally { Remove-Variable token -ErrorAction SilentlyContinue }
```

The endpoint is `http://localhost:8000` for host-local development; remote
endpoints require **HTTPS**. The tool refuses nonlocal cleartext HTTP,
credentials, query parameters and path prefixes in the base URL.

## Expected observations — explicitly check in browser

The script prints a unique **run ID, trace ID, UTC timestamp, service identities
and host name**, never the key. `HTTP 200` means the ingestion endpoint accepted
three requests; **it is not proof of query persistence**.

1. In the **same project**, select the 1h window containing the UTC timestamp.
   Services should show `m6-acceptance-gateway`, `m6-acceptance-checkout`, and
   `m6-acceptance-payments`, all with environment `acceptance`.
2. Open **Observed relationships**. For the fresh trace, expect exactly
   `gateway → checkout` and `checkout → payments`, supported by real matching
   trace/parent IDs; use its trace link to inspect the three spans in Traces.
   Earlier accepted telemetry can produce unrelated additional relationships.
3. Search Metrics for `sentrix.m6.acceptance.requests`; inspect the three gauge
   records. Search Logs for `M6 acceptance`; inspect matching trace IDs.
4. In Infrastructure verify that only observed `host.name`, `k8s.cluster.name`,
   `k8s.namespace.name`, `k8s.pod.name` and `k8s.container.name` values
   appear. Three distinct pod/resource combinations share the unique host name;
   no actual Kubernetes API or node-health assertion is established.
5. Switch to a **different project** and confirm none of the run's unique
   identifiers appear there. Independently test a **separate user** lacking
   membership in the populated project, which must receive `404` for its
   authenticated read endpoints (not merely another project of the same user).
6. Manually test window boundaries, empty states, simulated dependency failure
   and truncation where safe, keyboard/focus/mobile and localStorage stale
   recovery. Do not mark unobserved states as passed. The script cannot prove
   those results and does not induce failures for you.
7. Record operator/date, tested SHA, actual observations, run/trace IDs (no
   credential), foreign-user result, UI observations and hosted CI link in
   `M6_2_BROWSER_ACCEPTANCE.md`, `M6_3_BROWSER_ACCEPTANCE.md`, and
   `M6_4_BROWSER_ACCEPTANCE.md`. Leave missing cases **Not run** or **Blocked**.
8. Revoke the temporary key from project Settings, run `scripts/verify.ps1`,
   and commit acceptance evidence only after the required cases have passed.

Because this script emits controlled fixtures, the acceptance checklists must
still record a separately instrumented real framework/application or Collector
producer when claiming external application onboarding. Never substitute this
smoke alone for that required external application evidence.

## Focused checks

```powershell
docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_m6_acceptance_smoke.py -v
.\scripts\verify.ps1
```

Failures include `401`/`403` project-key rejection, `400`/`415` wrong protocol,
`503` persistence failure or transport connection errors. The tool reports only
safe status/error categories and does not dump response bodies or credentials.
