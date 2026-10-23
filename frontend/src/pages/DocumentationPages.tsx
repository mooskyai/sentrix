import { useState } from "react";
import { Link } from "react-router-dom";

const pythonExample = `import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider(resource=Resource.create({
    "service.name": "checkout",
    "deployment.environment.name": "development",
}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
    endpoint="http://localhost:8000/v1/traces",
    headers={"Authorization": f"Bearer {os.environ['SENTRIX_API_KEY']}"},
)))
trace.set_tracer_provider(provider)
with trace.get_tracer("sentrix-setup").start_as_current_span("hello-sentrix"):
    pass
provider.force_flush()
provider.shutdown()`;

function DocumentationHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="page-heading workspace-heading">
      <div>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      <Link to="/" className="button secondary inline-button">Back to overview</Link>
    </div>
  );
}

type Framework = "laravel" | "node" | "react" | "next";
const frameworkOrder: Framework[] = ["laravel", "node", "react", "next"];
const frameworkGuides = {
  laravel: {
    label: "Laravel (PHP)",
    short: "PHP server · automatic request spans",
    installTitle: "Install PHP OpenTelemetry instrumentation",
    install: "pecl install opentelemetry\n# Enable extension=opentelemetry.so in your PHP configuration\ncomposer require open-telemetry/sdk open-telemetry/exporter-otlp php-http/guzzle7-adapter open-telemetry/opentelemetry-auto-laravel",
    configureTitle: "Configure the PHP process (server environment only)",
    configure: "OTEL_PHP_AUTOLOAD_ENABLED=true\nOTEL_SERVICE_NAME=laravel-api\nOTEL_TRACES_EXPORTER=otlp\nOTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf\nOTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000\nOTEL_EXPORTER_OTLP_HEADERS=\"Authorization=Bearer%20<YOUR_SENTRIX_PROJECT_KEY>\"\nOTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=development",
    launchTitle: "Restart and generate a real request",
    launch: "php --ri opentelemetry\nphp artisan serve\n# Visit a Laravel route in the browser, then check Sentrix Services.",
    note: "Install and enable the PHP extension on the same PHP runtime that serves Laravel (including PHP-FPM or workers). The .env format shown is illustrative; load variables in the actual PHP process, then restart it. Do not commit a real key.",
    link: "https://opentelemetry.io/docs/zero-code/php/auto/"
  },
  node: {
    label: "Node.js",
    short: "Node server · HTTP and framework tracing",
    installTitle: "Install the OpenTelemetry Node SDK",
    install: "npm install @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-http",
    configureTitle: "Create instrumentation.cjs (load before your server starts)",
    configure: "const { NodeSDK } = require(\"@opentelemetry/sdk-node\");\nconst { OTLPTraceExporter } = require(\"@opentelemetry/exporter-trace-otlp-http\");\nconst { getNodeAutoInstrumentations } = require(\"@opentelemetry/auto-instrumentations-node\");\n\nconst sdk = new NodeSDK({\n  serviceName: \"node-api\",\n  traceExporter: new OTLPTraceExporter({\n    url: `${process.env.SENTRIX_OTLP_BASE_URL}/v1/traces`,\n    headers: { Authorization: `Bearer ${process.env.SENTRIX_API_KEY}` },\n  }),\n  instrumentations: [getNodeAutoInstrumentations()],\n});\nsdk.start();",
    launchTitle: "Set server secrets and launch Node (PowerShell)",
    launch: "$env:SENTRIX_API_KEY = \"<YOUR_SENTRIX_PROJECT_KEY>\"\n$env:SENTRIX_OTLP_BASE_URL = \"http://localhost:8000\"\nnode --require ./instrumentation.cjs server.js",
    note: "Replace server.js with your actual Node entry point. Install/start tracing before importing the app. This example exports traces; metrics/logs need their own configured exporters. Do not place the secret in browser-delivered JavaScript.",
    link: "https://opentelemetry.io/docs/languages/js/getting-started/nodejs/"
  },
  react: {
    label: "React (Vite)",
    short: "Browser app · use your backend safely",
    installTitle: "Connect the backend your React app already calls",
    install: "Use the Node.js or Laravel guide to instrument your server.\nNo Sentrix API key is needed in the React bundle.",
    configureTitle: "Keep API requests normal in your React app",
    configure: "// Example only: replace /api/orders with YOUR existing server route.\nexport async function loadOrders() {\n  const response = await fetch(\"/api/orders\");\n  if (!response.ok) throw new Error(\"Orders request failed\");\n  return response.json();\n}",
    launchTitle: "Generate traffic and inspect server traces",
    launch: "npm run dev\n# Visit a page that calls your instrumented backend.\n# Then check the backend service in Sentrix Services.",
    note: "React runs in the visitor’s browser: VITE_ variables are public. Never put a Sentrix project API key in VITE_*, frontend source, localStorage, or a direct browser OTLP request. This guide captures backend/server traffic; it does not claim direct browser telemetry ingestion is supported.",
    link: "https://opentelemetry.io/docs/languages/js/getting-started/browser/"
  },
  next: {
    label: "Next.js",
    short: "Next server · Node runtime only",
    installTitle: "Install a server-side trace exporter",
    install: "npm install @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http",
    configureTitle: "Add instrumentation.ts and instrumentation.node.ts",
    configure: "// instrumentation.ts (project root or src/)\nexport async function register() {\n  if (process.env.NEXT_RUNTIME === \"nodejs\") {\n    await import(\"./instrumentation.node\");\n  }\n}\n\n// instrumentation.node.ts (same directory)\nimport { NodeSDK } from \"@opentelemetry/sdk-node\";\nimport { OTLPTraceExporter } from \"@opentelemetry/exporter-trace-otlp-http\";\n\nconst sdk = new NodeSDK({\n  serviceName: \"next-server\",\n  traceExporter: new OTLPTraceExporter({\n    url: `${process.env.SENTRIX_OTLP_BASE_URL}/v1/traces`,\n    headers: { Authorization: `Bearer ${process.env.SENTRIX_API_KEY}` },\n  }),\n});\nsdk.start();",
    launchTitle: "Use private server environment variables",
    launch: "SENTRIX_API_KEY=<YOUR_SENTRIX_PROJECT_KEY>\nSENTRIX_OTLP_BASE_URL=http://localhost:8000\n# Restart the Next.js server and request a page/API route.",
    note: "Set values as server-only deployment secrets, not NEXT_PUBLIC_ variables. The instrumentation.node.ts module must never run in the Edge runtime or browser. If deploying Next.js remotely, replace localhost with a reachable secured HTTPS Sentrix origin.",
    link: "https://nextjs.org/docs/app/guides/instrumentation"
  }
} as const;

function CopyableSnippet({ label, content }: { label: string; content: string }) {
  const [copyStatus, setCopyStatus] = useState("Copy");
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopyStatus("Copied");
    } catch {
      setCopyStatus("Copy unavailable");
    }
  }
  return (
    <div className="docs-snippet">
      <div className="docs-snippet-toolbar">
        <strong>{label}</strong>
        <button className="button secondary" type="button" onClick={() => void copy()}>{copyStatus}</button>
      </div>
      <pre><code>{content}</code></pre>
    </div>
  );
}

export function TelemetrySetupPage() {
  const [framework, setFramework] = useState<Framework>("node");
  const guide = frameworkGuides[framework];
  return (
    <>
      <DocumentationHeader
        title="Documentation"
        description="Connect your project with a few steps. Choose your application framework below."
      />
      <section className="workspace-section workspace-section--surface" aria-label="Telemetry setup documentation">
        <div className="grid gap-3 docs-quickstart">
          <p className="muted">Getting started · OpenTelemetry OTLP/HTTP protobuf · no Sentrix-specific SDK required</p>
          <h2>Step 1 — Choose your Sentrix project</h2>
          <p>Use the organization and project selectors at the top. Open <strong>Settings</strong>, enter a name
            such as “Development server”, and click <strong>Create API key</strong>. Owners, admins and editors
            can create keys; viewers can read these instructions but cannot manage secrets.</p>
          <p><strong>Copy the raw secret immediately.</strong> It is shown only once. Store it as a
            server-side environment variable or secret-manager value. Never paste it into browser code,
            screenshots or Git. Keys have <code>telemetry:write</code> scope.</p>
          <h2>Step 2 — Choose your framework</h2>
          <div className="docs-frameworks" aria-label="Choose your application framework">
            {frameworkOrder.map((item) => (
              <button
                key={item}
                type="button"
                className={`docs-framework ${framework === item ? "is-selected" : ""}`}
                aria-pressed={framework === item}
                onClick={() => setFramework(item)}
              >
                <strong>{frameworkGuides[item].label}</strong>
                <small>{frameworkGuides[item].short}</small>
              </button>
            ))}
          </div>
          <section className="docs-platform-guide" aria-live="polite" aria-label={`${guide.label} setup instructions`}>
            <h3>{guide.label} setup</h3>
            <p className="muted">These commands run in your application project, not inside Sentrix.</p>
            <CopyableSnippet key={`${framework}-install`} label={`1. ${guide.installTitle}`} content={guide.install} />
            <CopyableSnippet key={`${framework}-configure`} label={`2. ${guide.configureTitle}`} content={guide.configure} />
            <CopyableSnippet key={`${framework}-launch`} label={`3. ${guide.launchTitle}`} content={guide.launch} />
            <p className="notice">{guide.note}</p>
            <p className="muted">Framework documentation: <a href={guide.link} target="_blank" rel="noreferrer">Open upstream guide</a></p>
          </section>
          <h2>Step 3 — Confirm data appears</h2>
          <p>Use <code>http://localhost:8000</code> from the Windows host, <code>http://api:8000</code>
            from a container on the Sentrix Compose network, or a reachable HTTPS URL for remote apps.
            The exporter must send <code>application/x-protobuf</code> to <code>/v1/traces</code>,
            <code>/v1/metrics</code> or <code>/v1/logs</code> (no trailing slash), with a
            <code> Bearer</code> project key. These are machine-ingest paths, not browser-session APIs.</p>
          <p>Trigger a real server request, select the <strong>same project</strong>, then look for the
            observed service in <strong>Services</strong> with a time window covering the request.
            This shows evidence of telemetry receipt, not service health.</p>
          <h2>Need a quick smoke test?</h2>
          <p>Python can send a single sample trace without changing your application:</p>
          <CopyableSnippet label="Install Python OTLP exporter" content="pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http" />
          <CopyableSnippet label="Set the key in PowerShell" content={'$env:SENTRIX_API_KEY = "<YOUR_SENTRIX_PROJECT_KEY>"'} />
          <CopyableSnippet label="send_span.py — run with python send_span.py" content={pythonExample} />
          <h2>Troubleshooting</h2>
          <ul>
            <li><strong>Nothing appears:</strong> check API/ClickHouse containers, the exporter URL,
              project key, server activity and selected observation window.</li>
            <li><strong>401:</strong> missing, expired, revoked or wrong project key; generate a new one in Settings.</li>
            <li><strong>403:</strong> key lacks the <code>telemetry:write</code> scope.</li>
            <li><strong>400/415:</strong> malformed request or non-protobuf content type.</li>
            <li><strong>413:</strong> telemetry request exceeded the limit.</li>
            <li><strong>503:</strong> durable ClickHouse ingestion is unavailable.</li>
          </ul>
          <p className="muted">This guide is for sending data. Read/manage control-plane APIs require
            a logged-in browser session; a telemetry key cannot list projects or create other keys.</p>
        </div>
      </section>
    </>
  );
}

export function ApiReferencePage() {
  return (
    <>
      <DocumentationHeader
        title="Sentrix API reference"
        description="Authentication, endpoint paths, request formats, limits, and common responses."
      />
      <section className="workspace-section workspace-section--surface" aria-label="API documentation">
        <div className="grid gap-3">
          <h2>Base URLs and authentication</h2>
          <p><code>http://localhost:8000/api/v1/</code> is the local control-plane API for browser sessions.
            Read and management endpoints require login membership; write operations require CSRF and
            the appropriate organization role. A project telemetry key does <strong>not</strong> authorize them.</p>
          <p><code>http://localhost:8000/v1/</code> is the independent OTLP/HTTP machine interface.
            Supply <code>Authorization: Bearer sentrix_pk_...</code> with <code>telemetry:write</code>.
            Only binary protobuf is accepted; sending arbitrary JSON will fail.</p>
          <h2>Authentication and control plane</h2>
          <div className="metric-table-wrap"><table className="metric-table"><thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead><tbody>
            <tr><td>GET</td><td><code>/api/v1/health/live/</code></td><td>Liveness</td></tr>
            <tr><td>GET</td><td><code>/api/v1/health/ready/</code></td><td>Database and service readiness</td></tr>
            <tr><td>GET</td><td><code>/api/v1/auth/csrf/</code></td><td>Get CSRF token/cookie</td></tr>
            <tr><td>POST</td><td><code>/api/v1/auth/login/</code></td><td>Log in with username and password</td></tr>
            <tr><td>POST</td><td><code>/api/v1/auth/logout/</code></td><td>End session</td></tr>
            <tr><td>GET</td><td><code>/api/v1/auth/me/</code></td><td>Current account</td></tr>
            <tr><td>GET, POST</td><td><code>/api/v1/organizations/</code></td><td>Member organizations / create</td></tr>
            <tr><td>GET, POST</td><td><code>/api/v1/projects/</code></td><td>Accessible projects / create</td></tr>
            <tr><td>GET, POST</td><td><code>/api/v1/projects/&#123;project_id&#125;/api-keys/</code></td><td>Manage credentials, write roles only</td></tr>
            <tr><td>DELETE</td><td><code>/api/v1/projects/&#123;project_id&#125;/api-keys/&#123;key_id&#125;/</code></td><td>Revoke credential</td></tr>
          </tbody></table></div>
          <h2>OTLP ingestion</h2>
          <div className="metric-table-wrap"><table className="metric-table"><thead><tr><th>Method</th><th>Path</th><th>Content type</th></tr></thead><tbody>
            <tr><td>POST</td><td><code>/v1/traces</code></td><td><code>application/x-protobuf</code></td></tr>
            <tr><td>POST</td><td><code>/v1/metrics</code></td><td><code>application/x-protobuf</code></td></tr>
            <tr><td>POST</td><td><code>/v1/logs</code></td><td><code>application/x-protobuf</code></td></tr>
          </tbody></table></div>
          <p>OTLP responses return 200 after durable non-empty ingestion, 400 for invalid wire payload,
            401 for invalid keys, 403 for missing scope, 413 for oversized payloads, 415 for unsupported
            types/encoding and 503 when persistence is unavailable.</p>
          <h2>Project telemetry reads (session-authenticated)</h2>
          <p>Prefix the paths below with <code>/api/v1/projects/&#123;project_id&#125;</code>.
            The server resolves the authorized tenant from the logged-in user, not caller-supplied organization IDs.</p>
          <div className="metric-table-wrap"><table className="metric-table"><thead><tr><th>GET path</th><th>Input and result</th></tr></thead><tbody>
            <tr><td><code>/services/catalog/</code></td><td>Service/environment counts, first/last seen, truncation. 24h default, 7d maximum, limit 1–500.</td></tr>
            <tr><td><code>/services/detail/</code></td><td>Required exact <code>service_name</code> and <code>environment</code>, bounded metric names, errors and trace references.</td></tr>
            <tr><td><code>/metrics/catalog/</code></td><td>Observed numeric metric catalog for a bounded window.</td></tr>
            <tr><td><code>/metrics/series/</code></td><td>Required <code>metric_name</code>, optional exact service/environment, bounded scalar series.</td></tr>
            <tr><td><code>/logs/search/</code></td><td>Optional service, environment, severity, body substring, trace ID; limit up to 1000.</td></tr>
            <tr><td><code>/traces/&#123;trace_id&#125;/</code></td><td>Exact 32-character nonzero hex trace ID; bounded raw spans (max 1000).</td></tr>
          </tbody></table></div>
          <p>Query windows use timezone-aware RFC3339 <code>start</code> and <code>end</code>, with an
            exclusive end and a maximum duration of seven days. Most explorers default to one hour;
            Services defaults to 24 hours. Nonexistent or foreign projects return a nondisclosing 404.
            Empty results do not mean infrastructure or services are down.</p>
          <h2>Dashboards, alerts and notifications</h2>
          <p>Authenticated project members can read applicable state; owners/admins/editors manage it.</p>
          <ul>
            <li><code>GET, POST /api/v1/projects/&#123;project_id&#125;/dashboard-panels/</code>; DELETE with <code>/&#123;panel_id&#125;/</code> (maximum six panels).</li>
            <li><code>GET, POST /api/v1/projects/&#123;project_id&#125;/alert-rules/</code>; GET/PATCH/DELETE with <code>/&#123;rule_id&#125;/</code>.</li>
            <li><code>GET, POST /api/v1/projects/&#123;project_id&#125;/notification-channels/</code>; GET/PATCH/DELETE with <code>/&#123;channel_id&#125;/</code>.</li>
            <li><code>GET /api/v1/projects/&#123;project_id&#125;/notification-deliveries/?limit=100</code> for bounded delivery history.</li>
          </ul>
          <h2>Errors and security</h2>
          <p><strong>400</strong> invalid input; <strong>401/403</strong> missing credentials or insufficient
            access; <strong>404</strong> unknown or foreign project; <strong>413</strong> oversized OTLP;
            <strong>415</strong> unsupported wire format; <strong>503</strong> unavailable telemetry query/persistence.
            Control-plane URLs use trailing slashes; the three OTLP ingest URLs do not.</p>
          <p>Never send a telemetry API key to a session-authenticated management endpoint. API key
            creation returns the secret only once. The repository <code>API.md</code> documents
            additional request/response shapes and the current milestone contracts.</p>
          <p><Link to="/docs/telemetry-setup">Follow the project API-key setup guide</Link>.</p>
        </div>
      </section>
    </>
  );
}
