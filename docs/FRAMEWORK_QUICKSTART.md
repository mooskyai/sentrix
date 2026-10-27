# Framework setup quickstart for Sentrix

## M7.3.3a Next.js server fixture — local acceptance verified (CI open)

The isolated Next.js App Router Node fixture at `integrations/m7-nextjs-node`
performs a real server request and a manually instrumented OpenTelemetry
`SERVER` span. See [Next.js runtime acceptance](M7_NEXT_RUNTIME_ACCEPTANCE.md)
for a secret-safe stdin probe, fake receiver checks, independently scoped
ClickHouse verifier and outstanding operator gates. It is not Edge/browser
instrumentation or proof of automatic framework tracing. Do not mark Next.js
released until lockfile review, final commit and exact-SHA CI pass.
All three browser checks and same-key revocation were operator-confirmed.
Local producer/read-back and API isolation results are in
[M7.3.3a evidence](M7_3_3A_LOCAL_EVIDENCE_2026_10_27.md).

## M7.3.2 Node runtime proof (candidate)

A separate runnable Node.js/Express HTTP+OpenTelemetry SDK example and
project-scoped persistence verifier are documented at
[M7 Node runtime acceptance](M7_NODE_RUNTIME_ACCEPTANCE.md). It tests
manual server spans only. Do not assume existing Node/Next.js quickstart
recipes are production-certified; remote export requires HTTPS and server-held
API keys, with `application/x-protobuf` at `/v1/traces`.

## M7.3.1 Django runtime example — manual tracing

Use [the isolated Django WSGI runtime acceptance guide](M7_DJANGO_RUNTIME_ACCEPTANCE.md)
for a runnable upstream SDK trace export followed by an independent
ClickHouse read-back. It proves only the specifically instrumented manual
Django `SERVER` span after real operator execution; it is **not** automatic
framework instrumentation for an existing Django installation. Keep API keys
outside browser bundles and record missing runtime checks honestly.

## M7.2 guided Django and Node service check — candidate

Open a particular project's **Settings → Connect an application** to select
Django/Python or Node.js/Express. Choose exporter location from the server's
network namespace (Windows host, same Sentrix Compose network, or remote
HTTPS root), then copy placeholder-only **server** commands and issue an
actual application request. **Check service** queries exact `service.name`
and `deployment.environment.name` from the authorized project's persisted
Services catalog in a 24-hour UTC window, not from OTLP write credentials.
A match means rows exist; absent in a truncated result is inconclusive. This
guide currently emits traces only, and its examples are not independently
runtime-certified. See [M7 guided runbook](M7_GUIDED_INTEGRATIONS.md).

## M7.1 stored-telemetry check — implementation candidate

After triggering a real server request, choose the same project and open
**Settings → First telemetry check**. The on-demand check shows per-signal
sample counts and latest observed timestamps for a 24-hour UTC window.
A zero result means no stored sample in that window, not a failed key or
unreachable exporter; a query error is displayed separately. Use the existing
Services/Traces/Logs explorers for detail. This diagnostic is **not** proof
that a Laravel, Node, Next.js, Django or Collector recipe has been
independently verified in a running application. Keep project keys server-only.

## Roadmap and evidence status (2026-10-24)

The in-app framework choices are **onboarding recipes**, not a certified SDK
compatibility matrix. At `0939cca` this guide and its sidebar entry are pushed;
full automated tests were user-reported as green, but per-framework real-app
smoke tests and M6.2/M6.3 operator acceptance remain open. See
[ROADMAP.md](../ROADMAP.md) for the required Laravel/Node/Next/Django/Collector
runtime acceptance matrix. React uses an instrumented backend until a separate
browser-safe data ingestion design exists. Never put keys in `VITE_*` or
`NEXT_PUBLIC_*` environment values.

The in-app **Documentation** link in the left sidebar (`/docs/telemetry-setup`) provides copyable, selectable framework recipes. The old API reference remains directly routable (`/docs/api-reference`) but has no navigation links while setup takes priority.

## Prerequisites

1. In Sentrix select your organization and project. Under **Settings**, create a `telemetry:write` API key. Owners/admins/editors may create; viewers can read docs.
2. Copy the complete raw key **once** into a server-side secret manager. It cannot be retrieved from the listing; never paste it into browser/React/Next `NEXT_PUBLIC_`/Vite `VITE_` environments or screenshots.
3. Choose the exporter origin from the **exporter's own network namespace**: `http://localhost:8000` for an app on the Windows host, `http://api:8000` for a container on the same Compose network, and a protected HTTPS address from a remote service. `localhost` inside an unrelated container is not Sentrix.
4. Sentrix implements **OTLP/HTTP binary protobuf** with project Bearer authorization, **not** OTLP JSON or gRPC. Append `/v1/traces`, `/v1/metrics`, `/v1/logs` with **no** trailing slash. The API key does not authorize `/api/v1/` management endpoints.

## Laravel (PHP server)

Install the PECL `opentelemetry` extension, enable it in the PHP configuration of the process serving Laravel, then run:

```bash
composer require open-telemetry/sdk open-telemetry/exporter-otlp php-http/guzzle7-adapter open-telemetry/opentelemetry-auto-laravel
```

Configure the **server process** with:

```dotenv
OTEL_PHP_AUTOLOAD_ENABLED=true
OTEL_SERVICE_NAME=laravel-api
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer%20<YOUR_SENTRIX_PROJECT_KEY>"
OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=development
```

Store key in a secret manager and use the actual endpoint for the running PHP host/container; do not commit a populated `.env`. Restart PHP-FPM/worker processes and make an application request. Installation of the extension without the SDK and an instrumentation library does not create traces. See https://opentelemetry.io/docs/zero-code/php/auto/.

## Node.js (backend)

```bash
npm install @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-http
```

Create `instrumentation.cjs`:

```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const sdk = new NodeSDK({
  serviceName: 'node-api',
  traceExporter: new OTLPTraceExporter({
    url: `${process.env.SENTRIX_OTLP_BASE_URL}/v1/traces`,
    headers: { Authorization: `Bearer ${process.env.SENTRIX_API_KEY}` },
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});
sdk.start();
```

Set `SENTRIX_API_KEY` and `SENTRIX_OTLP_BASE_URL` as **server-side** environment variables and start the application with `node --require ./instrumentation.cjs server.js` (replace `server.js` with your entry point). This example configures a trace exporter, not automatic metrics/logs export. See https://opentelemetry.io/docs/languages/js/getting-started/nodejs/.

## React (Vite browser UI)

Never send a project API key directly from the React browser. `VITE_` environment variables ship to end users and are **not secrets**. Instead, instrument your existing Node/Laravel API server using the server guides above and call its ordinary routes from React. Requests to instrumented server endpoints produce server-side observations; they do not require sending the Sentrix key to the browser. React browser tracing via your own secure authenticated gateway is a separate integration, **not** an implemented Sentrix endpoint.

## Next.js (Node server runtime only)

Install `@opentelemetry/sdk-node` and `@opentelemetry/exporter-trace-otlp-http`. Put `instrumentation.ts` at project root or under `src/`:

```typescript
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('./instrumentation.node');
  }
}
```

In `instrumentation.node.ts` (same folder), configure the Node runtime exporter:

```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';

const sdk = new NodeSDK({
  serviceName: 'next-server',
  traceExporter: new OTLPTraceExporter({
    url: `${process.env.SENTRIX_OTLP_BASE_URL}/v1/traces`,
    headers: { Authorization: `Bearer ${process.env.SENTRIX_API_KEY}` },
  }),
});
sdk.start();
```

Keep both server values out of `NEXT_PUBLIC_` and ensure the instrumentation module never imports into an Edge or browser bundle. See https://nextjs.org/docs/app/guides/instrumentation.

## Verify and troubleshoot

Generate a real server request and open the matching Sentrix project → **Services**, with the last 1h/24h time window including the request. A service record proves ingestion, not runtime health. `401`: wrong/expired/revoked credential; `403`: insufficient scope; `400/415`: malformed or non-protobuf OTLP; `413`: oversized batch; `503`: ClickHouse ingestion unavailable. `No observations`: check server logs, exporter flush, connectivity and time window. The Python smoke test remains in [PROJECT_TELEMETRY_SETUP.md](PROJECT_TELEMETRY_SETUP.md).

Framework recipes follow upstream OpenTelemetry SDKs and do not add a Sentrix-specific SDK or proxy. They must be exercised in the user's real application environments before claiming runtime verification.
