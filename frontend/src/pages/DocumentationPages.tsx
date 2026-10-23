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

export function TelemetrySetupPage() {
  return (
    <>
      <DocumentationHeader
        title="Connect telemetry using a project API key"
        description="Send real OpenTelemetry traces, metrics, and logs to your selected Sentrix project."
      />
      <section className="workspace-section workspace-section--surface" aria-label="Telemetry setup documentation">
        <div className="grid gap-3">
          <h2>1. Create a project credential</h2>
          <p>Choose your organization and project using the selectors in the upper-right corner, then open
            <strong> Settings</strong>. Owners, admins, and editors can create a project API key. Name it for
            the collector or application and optionally set an expiry.</p>
          <p>Click <strong>Create API key</strong> and copy the raw secret immediately. It is displayed once.
            Keys have the <code>telemetry:write</code> scope. Viewers can inspect telemetry but cannot create keys.</p>
          <h2>2. Choose an endpoint</h2>
          <p>For Sentrix running on your Windows host with Docker Compose, use
            <code> http://localhost:8000</code>. From another container on the same Compose network,
            use <code>http://api:8000</code>. Remote collectors need an HTTPS address reachable from
            their environment; do not expose the local development server directly to the internet.</p>
          <p>The OTLP/HTTP protobuf ingestion paths have <strong>no trailing slash</strong>:</p>
          <ul>
            <li><code>POST /v1/traces</code></li>
            <li><code>POST /v1/metrics</code></li>
            <li><code>POST /v1/logs</code></li>
          </ul>
          <p>Use <code>Authorization: Bearer &lt;project API key&gt;</code> and
            <code> Content-Type: application/x-protobuf</code>. JSON OTLP bodies are not supported.</p>
          <h2>3. Send a first trace from Python</h2>
          <pre style={{ overflowX: "auto" }}><code>pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http</code></pre>
          <p>In PowerShell set the secret only for the current session (do not paste real keys in shared logs):</p>
          <pre style={{ overflowX: "auto" }}><code>{'$env:SENTRIX_API_KEY = "<copy-your-one-time-secret>"'}</code></pre>
          <p>Save the following as <code>send_span.py</code> and run <code>python send_span.py</code>:</p>
          <pre style={{ overflowX: "auto" }}><code>{pythonExample}</code></pre>
          <p>For remote deployment change the exporter endpoint to the correct HTTPS origin.
            A real exporter should set <code>service.name</code> and, where available,
            <code>deployment.environment.name</code> in its OpenTelemetry resource attributes.</p>
          <h2>4. Confirm data in Sentrix</h2>
          <p>Return to the same project and open <strong>Traces</strong> or <strong>Services</strong>.
            Use the observation window covering your export time. The presence of a service only proves
            it was observed in telemetry; it does not prove health or availability.</p>
          <h2>Common problems</h2>
          <ul>
            <li><strong>401</strong>: key missing, expired, revoked, or incorrect. Create a new key if the one-time secret was lost.</li>
            <li><strong>403</strong>: missing <code>telemetry:write</code> scope.</li>
            <li><strong>400/415</strong>: invalid protobuf payload, content type or encoding.</li>
            <li><strong>413</strong>: payload exceeds the configured request limit.</li>
            <li><strong>503</strong>: telemetry persistence is unavailable; check ClickHouse and API logs.</li>
            <li><strong>No observations</strong>: confirm collector network access, correct project key, successful export and observation window.</li>
          </ul>
          <p>Keep the raw key out of source control, URLs, screenshots and browser storage. Revoke a compromised
            key from project Settings and replace it in your collector.</p>
          <p><Link to="/docs/api-reference">See the detailed Sentrix API reference</Link>.</p>
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
