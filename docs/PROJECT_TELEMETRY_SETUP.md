# Connect a Sentrix project to OpenTelemetry

This guide describes the **implemented** Sentrix OTLP/HTTP binary-protobuf interface. The same guide is reachable from a project's **Settings → Telemetry setup guide** link; it is not a new workspace tab.

## 1. Create the project key

1. Sign in, select an organization and an authorized project in the shared header, then open **Settings**.
2. With owner, admin or editor access, enter a credential name and optional expiry. Click **Create API key**.
3. Copy the raw `sentrix_pk_...` value once; it is not retrievable from subsequent GET requests. Store it in your deployment secret manager. Do not commit it or put it in a URL.
4. Send telemetry with `Authorization: Bearer <raw-project-key>`. This credential has `telemetry:write` and **cannot** authorize `/api/v1/` browser/control-plane routes.

## 2. Endpoints

For a collector running on the same Windows machine as the Docker Compose stack, the local base origin is `http://localhost:8000`. Another container on the Compose network can reach `http://api:8000`. Use a secured HTTPS origin for remote exporters.

| Signal | OTLP/HTTP POST path |
| --- | --- |
| Traces | `/v1/traces` |
| Metrics | `/v1/metrics` |
| Logs | `/v1/logs` |

Set `Content-Type: application/x-protobuf`; binary protobuf only. `identity` or `gzip` content encoding is supported. **These paths have no trailing slash.** Don't send OTLP JSON and don't send control-plane session cookies to these endpoints.

## 3. Python trace smoke

```powershell
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
$env:SENTRIX_API_KEY = '<the one-time project key>'
python .\send_span.py
```

Save as `send_span.py`:

```python
import os
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
provider.shutdown()
```

From a different machine, replace `localhost:8000` with the authenticated HTTPS endpoint. For all three signals, a collector may send OTLP/HTTP protobuf to the respective path using the same project key.

## 4. Verify and troubleshoot

Return to the same project, open **Services** or **Traces**, and choose an observation window that includes the export. No observation is not evidence of downtime.

- `401`: invalid/missing/revoked/expired key.
- `403`: missing `telemetry:write` scope.
- `400` / `415`: malformed protobuf, content type, or content encoding.
- `413`: oversized request.
- `503`: persistence unavailable (inspect ClickHouse and API logs, without logging secrets).

If you lose the one-time secret, create a replacement key and revoke the old key. Sending a project key in a browser session API request is unsupported. For query endpoints and control-plane authentication, see [API_REFERENCE.md](API_REFERENCE.md) and the repository root [API.md](../API.md).
