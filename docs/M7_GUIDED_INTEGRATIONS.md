# Sentrix M7.2 — Guided Django/Node server integration

**Status:** code/test candidate on `4116f08`, not certified runtime integration.
M6 human/browser acceptance and M7.1 independent runtime/browser acceptance remain open.

## Start in the authorized project

Sign in to Sentrix and open **Settings → Connect an application**. This does not
accept an API key: create a temporary `telemetry:write` key with an authorized
writer in **Settings → Project API keys**, copy it once into your **application's
private server environment**, and never put it in a browser, `VITE_*`,
`NEXT_PUBLIC_*`, Git, screenshots or the guided setup form.

Select **Node.js / Express** or **Django / Python**. Choose the exporter network:

- **Windows host:** `http://localhost:8000` only if the exporter itself runs
  on the Windows host that publishes the Sentrix API port.
- **Sentrix Compose network:** `http://api:8000` only for a process in a
  container on that exact Compose network. Another container's `localhost`
  points to itself, not the Sentrix API service.
- **Remote server:** enter a reachable protected **HTTPS root origin**.
  Paths, embedded credentials, fragments, query strings and HTTP are rejected.

Use valid exact `service.name` and `deployment.environment.name` values for
this process. The copied snippets contain no real credentials. Configure the
private environment variable and restart the real application process.

## Django (server side)

The guide installs Python's OpenTelemetry distro, OTLP/HTTP protobuf exporter
and Django instrumentation. The `opentelemetry-instrument` CLI runs Django
with `--noreload` in development to avoid autoreloader duplication. The encoded
`Authorization=Bearer%20...` header format is from upstream OTLP environment
configuration. It is a *trace-only* smoke. Deployments running Gunicorn,
ASGI workers or containers need separate startup/runtime verification; this
sample is not a production setup guarantee.

## Node.js / Express (server side)

The Node guide installs the SDK, OTLP trace exporter and auto-instrumentations;
`instrumentation.cjs` must preload before the server/framework entry point.
Generate a real HTTP request on that running server. This is a trace-only
example; configure independent metric/log exporters if required.

## Verify actual observed service

After sending a real request, click **Check service**. The browser calls the
existing `GET /api/v1/projects/{project_id}/services/catalog/` with a server
session, a bounded 24-hour UTC window and `limit=500`. No OTLP write key is
sent or checked. The response is matched on exact project, service and
environment. A match reports persisted metric/log/span counts; it **does not**
prove the exporter remains connected, the key is active, or the service is
healthy. An absent row without truncation means no match *in the returned
window*, not disconnected. A truncated catalog or 503 error is inconclusive.
A manual refresh issues a new bounded query, never background polling.

## Acceptance and troubleshooting

Use `V1_M7_MILESTONE_TESTING.md` GIN-001–GIN-008 and
`MILESTONE_ACCEPTANCE_CHECKLIST.md` M7.2-G01–G05. Test Django and Node in
separate real processes, capture safe SDK/runtime versions and timestamps,
compare against independently persisted ClickHouse data, sign in as an
independent foreign user and verify 404/no query, exercise no data/truncation/
503/project switches, inspect browser network for absence of raw credentials,
revoke test keys and record exact commit/CI. Do not claim acceptance from
copyable snippets, simulated data or an HTTP 200 alone.

Typical causes of no data: exporter ran in the wrong network namespace,
HTTP/gRPC protocol mismatch, missing/wrong/revoked `telemetry:write` project
key, wrong service/environment attributes, no server requests, unsent spans,
clock/window mismatch or ClickHouse unavailable. Use `Settings → First
telemetry check` for a project-wide three-signal summary, then the Services
workspace for detail. No probes, secret-read endpoint, browser OTLP or new
ClickHouse tables are introduced by M7.2.
