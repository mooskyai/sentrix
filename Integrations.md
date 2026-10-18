# Sentrix — Integrations and External Protocols

**Implemented:** OpenTelemetry OTLP/HTTP ingestion and outbound signed webhooks. **Not implemented:** generic integrations marketplace, Kubernetes API client, Slack/email-specific notifier, integrations polling framework.

## 1. OTLP/HTTP ingestion (implemented)

| Signal | Method/path | Wire format |
| --- | --- | --- |
| Metrics | `POST /v1/metrics` | official OpenTelemetry protobuf |
| Logs | `POST /v1/logs` | official OpenTelemetry protobuf |
| Traces | `POST /v1/traces` | official OpenTelemetry protobuf |

Use a project key carrying `telemetry:write`:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <project-key>
```

Those are **illustrative local configuration names**; inject the key through a protected environment/secrets mechanism rather than checking the example into source. Standard OTLP exporters with a base endpoint send to the corresponding `/v1/<signal>` paths. Supported content encoding: identity/gzip. OTLP JSON/HTTP, gRPC ingestion, Prometheus scraping, and Kafka ingest are not implemented.

The project key authenticates first, provides tenant IDs from the control plane, and permits acknowledgment **only after** durable ClickHouse write. Signal normalization preserves resource attributes and relevant service/environment fields; trace IDs persist for log/trace correlation. On 503, exporters should retry according to their own backoff policy.

## 2. Project API key lifecycle

An owner/admin/editor opens project Settings, creates a credential, and copies the returned secret once. Later API reads expose only safe prefix/scope/expiry/last-used/revocation metadata. Revoke before rotating collectors. Machine credentials are not browser sessions and grant no control-plane rights.

## 3. Signed webhook notification integration (implemented)

Project owner/admin/editor creates a webhook channel via `/api/v1/projects/{project_id}/notification-channels/`. The create result supplies a one-time `signing_secret`; later channel reads return only redacted `endpoint_display`. Destination hostname must be explicitly allowed by server egress policy, HTTPS unless explicitly permitted otherwise.

An alert rule transitions through the evaluator; enabled channels queue one `alert.firing` or direct `alert.recovered` delivery. The one-shot `dispatch_notifications` command sends requests with:

```text
Content-Type: application/json
X-Sentrix-Event: alert.firing | alert.recovered
X-Sentrix-Delivery: <stable delivery UUID>
X-Sentrix-Timestamp: <Unix seconds>
X-Sentrix-Signature: sha256=<HMAC hex digest>
```

Signing bytes are `timestamp ASCII + b"." + exact received JSON body`; key bytes are UTF-8 of `signing_secret`. A receiver must verify with a constant-time digest comparison, reject stale timestamps under its policy, and dedupe on delivery UUID because retries may duplicate network attempts. No response body or exception text is persisted by dispatcher. 2xx succeeds; 408/425/429/5xx and network failures retry (max 3); redirects and other 3xx/4xx fail terminally.

**Important:** No built-in scheduler: operators must run `evaluate_alerts` and `dispatch_notifications` explicitly or deploy an approved later scheduling layer. Delivery may be delayed indefinitely without an external caller.

## 4. Planned integration surfaces

- **M6 proposal:** OTel-derived service/host/Kubernetes attributes; does **not** call Kubernetes API or require cluster credentials.
- Later: collector deployment guides, integrations management UI, Slack/email-native adapters, ticketing, cloud APIs, scheduled polling, SSO, metrics scraping. None are current features.

## 5. Integration changes

Document version/protocol compatibility, machine auth, tenant attribution, retransmission/idempotency, timeout/retry, data fields, redaction, operational runbook and negative acceptance. Update `API.md`, `DATABASE.md` (if fields change), `Authentication&Security.md`, and `ProjectImplementation.md` in the same patch.

## 8. M6 telemetry-based service and infrastructure discovery (planned)

M6 discovery consumes **existing** authenticated OTLP/HTTP metrics/logs/traces. Service identity uses stored `service_name` and `environment`; host and Kubernetes hints come only from supported OpenTelemetry `resource_attributes` such as `host.name`, `k8s.cluster.name`, `k8s.namespace.name`, workload and pod/container labels **when actually present**. Missing attributes must remain unknown. Resource containment should rely only on attributes co-observed in supporting rows, never a name-only guess.

Cross-service relationships require two real stored spans with matching trace and parent span identity in the same authorized project; neither generic span links nor coincidental service names establish a dependency edge. No Kubernetes API/agent credential, new exporter protocol, collector installation, Slack/email adapter, webhook redesign, or external service discovery integration is part of the M6 planning patch. Update integration configuration and proof only in the slice that actually introduces it.
