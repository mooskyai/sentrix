# Framework setup quickstart for Sentrix

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
