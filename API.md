# Sentrix — HTTP and Worker API Reference

## M7.3.2 — existing wire contract, no new API

The external Express fixture posts binary OTLP protobuf to the existing
`POST /v1/traces` receiver with a server-held Bearer `telemetry:write` key.
HTTP 200 only acknowledges ingestion; independent ClickHouse evidence is
required. No new routes, request format, browser credentials or schema are
introduced by M7.3.2.

## M7.3.1 runtime example — no new HTTP API

The isolated Django runtime smoke sends standard `POST /v1/traces`
`application/x-protobuf` with a server-held `telemetry:write` Bearer key.
The read-back CLI uses Django's project-key authentication and tenant-scoped
ClickHouse queries; it creates **no** new browser session API or storage table.
The receipt verifies one exact `m7.django.checkout` span only after read-back;
it does not represent a service-health signal or an SDK compatibility guarantee.

## M7.2 exact service verification (reuse existing GET)

The guided Settings check calls the already shipped session-protected
`GET /api/v1/projects/{project_id}/services/catalog/` with UTC `start/end`
covering 24 hours and `limit=500`. Django alone derives tenant predicates
from membership; a project write key is **never** accepted as browser auth.
A matching `{service_name,environment}` row reports stored signal counts;
no exact row within a truncated catalog is inconclusive. API errors (including
503) are not empty successful results. M7.2 adds **no new API route**, schema
or active connection probe.

## M7.1 — first-telemetry observation endpoint (candidate)

`GET /api/v1/projects/{project_id}/integrations/connection-status/` uses a
Django browser session; authenticated project viewers and writers may read it.
The key-scoped OTLP Bearer credential cannot authorize this route. For a fixed
server-selected half-open 24h UTC window, three bounded, typed ClickHouse
queries return `{project_id, start, end, observation_state, signals}`. Each
signal (`metrics`, `logs`, `traces`) returns `{observed, count, last_seen}`.
`not_observed` means *zero stored rows in that window*, never a claim of
failed connectivity. Foreign/missing projects return 404 before opening
ClickHouse; anonymous callers return 401/403; query failures return a sanitized
503 rather than a misleading empty state. No user-controlled tenant IDs,
window or table names, secret values or raw telemetry are accepted/returned.

## M6.4 observed service map — candidate API

`GET /api/v1/projects/{project_id}/services/map/?start=RFC3339&end=RFC3339&limit=100`
uses Django session authentication and project membership before ClickHouse. Window
is UTC half-open, defaults to 24h and caps at 7d. Limit defaults to 100, range 1–500.
Response: `{project_id,start,end,limit,truncated,span_scan_truncated,scanned_spans,relationships}`.
Each relationship has `from_service`, `from_environment`, `to_service`,
`to_environment`, `span_pairs` and up to three real `trace_ids`. The maximum
raw span scan is 10,000 rows, queried with `LIMIT 10001` to detect truncation;
`truncated` is true for either an edge limit or the raw scan cap. `404` for
foreign/unknown projects without ClickHouse access; `400` bad bounds; `503`
dependency failure. No inferred links, health or background graph cache.

## M6.3 Infrastructure — implementation candidate (not accepted)

Candidate route: `GET /api/v1/projects/{project_id}/infrastructure/?start=...&end=...&limit=...`.
Session auth; membership lookup before ClickHouse. UTC half-open window defaults to 24h and caps
at 7d. Limit defaults to 100, range 1–500. Return
`{project_id,start,end,limit,truncated,observations:[{attributes,first_seen,last_seen,metric_points,log_records,span_records}]}`;
only nonempty supported attribute keys. Errors: 400 invalid, 404 foreign/unknown, 503 ClickHouse
unavailable. Query groups co-observed attributes, **not** inferred resource relationships.

## M6.2 service-detail API (implemented/pushed at `a0e7881`)

`GET /api/v1/projects/{project_id}/services/detail/?service_name=...&environment=...&start=RFC3339&end=RFC3339`
uses an authenticated browser session and resolves project membership before ClickHouse reads.
Both exact identity fields are required; `environment=` explicitly represents an empty environment.
`start`/`end` default to the previous 24h, accept timezone-aware RFC3339, and cap at 7d;
results use `[start,end)` in UTC. Invalid input is `400`, unknown/foreign project is `404`,
and query failure is `503`. The response includes `project_id`, `service_name`, `environment`,
`start`, `end`, and `metric_names` (max 50 `{name,point_count}`), `error_logs` (max 20
`{timestamp,severity_number,severity_text,body,trace_id}` with body clipped to 512 Unicode
characters and severity >=17), `trace_references` (max 50 `{trace_id,last_seen,span_records}`),
plus per-list `truncated` flags. No inferred service status or persistent inventory.
All queries use typed tenant UUIDs, exact string attributes, and timestamps.
This supersedes any earlier M6.2 notes that state no detail route exists.

## M6.1 implemented service catalog (accepted `2c1b5a2`)

`GET /api/v1/projects/{project_id}/services/catalog/?start=RFC3339&end=RFC3339&limit=100`
uses **browser session authentication** and authorizes the route project before telemetry access.
`start` and `end` are optional timezone-aware UTC-normalized, half-open `[start,end)` boundaries;
default is 24 hours, maximum is seven days; `limit` defaults to 100 and must be 1–500.

Response fields: `project_id`, UTC `start`, UTC `end`, `limit`, boolean `truncated`, and `services`.
Each service has exact `service_name` and `environment` (which may be empty), UTC `first_seen` and
`last_seen`, `metric_points`, `log_records`, `span_records`, and `signals` (subset of
`["metrics", "logs", "traces"]`). Counts describe stored rows in the requested window,
**not** service health or lifetime volume. Empty service names are excluded. Foreign/unknown project
returns `404` before ClickHouse; malformed window/limit returns `400`; dependency unavailable returns
`503`. No write or machine-key access. M6.1 runtime acceptance passed.

**Authority:** `backend/config/urls.py` and app `urls.py`, serializers and views. **Implemented V1 M1–M5 and M6.1 service catalog**; no infrastructure/Kubernetes endpoint yet. Trailing slashes are significant for the control-plane routes; public OTLP paths have **no trailing slash**.

## 1. Authentication modes

| Boundary | Authentication | Allowed principal |
| --- | --- | --- |
| `/api/v1/health/*` | public | anonymous |
| `/api/v1/auth/csrf/`, `/login/` | public bootstrap + CSRF-protected login | browser |
| `/api/v1/*` domain and telemetry read APIs | Django session cookie; state changes require CSRF | logged-in member |
| `/v1/{metrics,logs,traces}` | `Authorization: Bearer sentrix_pk_...`, `telemetry:write` | machine credential, **not session** |

## 2. System and authentication endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health/live/` | liveness |
| GET | `/api/v1/health/ready/` | PostgreSQL/Redis/ClickHouse readiness; 503 on unavailable dependencies |
| GET | `/api/v1/auth/csrf/` | obtain `csrfToken`/cookie |
| POST | `/api/v1/auth/login/` | username/password to session; login needs CSRF header |
| POST | `/api/v1/auth/logout/` | end session; 204 |
| GET | `/api/v1/auth/me/` | current user |

## 3. Organization, project, key, dashboard endpoints

| Methods | Path | Rules |
| --- | --- | --- |
| GET, POST | `/api/v1/organizations/` | list member orgs / create org + ownership |
| GET, PATCH | `/api/v1/organizations/{organization_id}/` | membership scoped; owners/admins update |
| GET, POST | `/api/v1/projects/` | list member projects / create with writable org membership |
| GET, PATCH, DELETE | `/api/v1/projects/{project_id}/` | project membership and role checks |
| GET, POST | `/api/v1/projects/{project_id}/api-keys/` | writable project roles; raw key only in create response |
| DELETE | `/api/v1/projects/{project_id}/api-keys/{api_key_id}/` | revoke project key |
| GET, POST | `/api/v1/projects/{project_id}/dashboard-panels/` | project members read, writers create, max 6 |
| DELETE | `/api/v1/projects/{project_id}/dashboard-panels/{panel_id}/` | writers delete |

## 4. Telemetry ingestion

```text
POST /v1/metrics
POST /v1/logs
POST /v1/traces
Authorization: Bearer sentrix_pk_<public-prefix>_<secret>
Content-Type: application/x-protobuf
Content-Encoding: identity | gzip
```

Only binary protobuf is supported. Project identity comes from a verified key, not from the request body. Non-empty data is acknowledged with HTTP 200 **only after** ClickHouse persistence. Typical failures: 400 malformed, 401 missing/invalid/revoked/expired key, 403 scope failure, 413 oversized, 415 unsupported encoding/type, 503 durable sink unavailable. `OTLP_MAX_REQUEST_BYTES` defaults to 64 MiB after decompression.

## 5. Session-authenticated telemetry reads

| GET route suffix after `/api/v1/projects/{project_id}` | Query contract |
| --- | --- |
| `/metrics/catalog/` | optional RFC3339 `start`, `end`, `limit<=500`; defaults 1h; max 7d |
| `/metrics/series/` | required `metric_name`; optional `start`, `end`, `limit<=5000`, exact `service_name`, `environment`; scalar points only |
| `/logs/search/` | bounded window; optional exact service/env, min severity 0–24, body substring, exact nonzero 32-hex trace ID; limit<=1000 |
| `/traces/{trace_id}/` | exact nonzero 32-hex trace ID, bounded `start/end`, `limit<=1000`; raw spans/parentage |

Queries use half-open `[start,end)` UTC RFC3339 windows; default last hour, maximum 7 days. Missing data yields healthy empty results; dependency failure returns **503**, not empty. Responses include bounded data and truncation where supported. Do not pass SQL fragments, caller-chosen org_id, or arbitrary unbounded filters.

## 6. Alerts and webhooks

| Methods | Route suffix after `/api/v1/projects/{project_id}` | Notes |
| --- | --- | --- |
| GET, POST | `/alert-rules/` | read member, write owner/admin/editor; max 50 |
| GET, PATCH, DELETE | `/alert-rules/{alert_rule_id}/` | exact project+rule scope |
| GET, POST | `/notification-channels/` | webhook channels; max 10; create returns signing secret once |
| GET, PATCH, DELETE | `/notification-channels/{channel_id}/` | endpoint returned redacted; never returns secret |
| GET | `/notification-deliveries/?limit=100` | bounded delivery status, max 500 |

Alert rule input: `name`, `metric_name`, `time_range` (`1h/6h/24h/7d`), optional exact `service_name`/`environment`, `comparator` (`gt/gte/lt/lte`), finite `threshold`, `enabled`. Read responses include current state: `pending/ok/firing/no_data/error/disabled` and bounded timestamps/code; **never raw sampled value**.

Channel input: `name`, `endpoint_url`, `enabled`. URL is write-only; list/detail return only `endpoint_display` with scheme/hostname and redaction. New signing secret is returned on create only. Delivery event type: `firing` or `recovered`; state: `pending/sending/retry/delivered/failed/cancelled`.

Webhook receiver must verify HMAC-SHA256 with the one-time channel signing secret over ASCII `X-Sentrix-Timestamp` + `.` + **exact received canonical JSON body**, comparing to `X-Sentrix-Signature: sha256=<hex>` using constant-time comparison. Metadata headers include `X-Sentrix-Delivery` and `X-Sentrix-Event: alert.firing|alert.recovered`.

## 7. One-shot operational commands (not HTTP routes)

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py evaluate_alerts --project-id <project-uuid>
docker compose exec -T api /opt/venv/bin/python manage.py dispatch_notifications --project-id <project-uuid>
```

The browser never evaluates metrics or dispatches notifications. The evaluator selects unique latest scalar points, writes current state, queues real transitions in the same transaction; the dispatcher claims due delivery rows and performs network I/O outside the transaction. **There is no built-in schedule**. See `Integrations.md`.

## 8. Error and versioning conventions

- `/api/v1/` is the current application prefix, `/v1/` is the independent OTLP wire protocol prefix.
- Foreign/unknown project or child resource: nondisclosing 404; invalid input: 400; insufficient role/scope: 403; auth error: 401/403 depending on authentication class; unavailable telemetry: 503.
- For exact field shapes, the serializers and endpoint tests are authoritative. When adding a route, update this document and `Authentication&Security.md` alongside tests.

## M6 interface work to design, not yet implemented

No service-catalog, host/Kubernetes inventory, or service-map API is present at the M5 baseline; do not call a guessed route or document its response as stable. M6.1 must first specify and test service catalog and detail contracts against existing ClickHouse data; M6.3 and M6.4 add only supported resource and evidence-backed relationship queries.

Each proposed session API must (1) authenticate a real user, (2) resolve project membership before creating a ClickHouse client, (3) take the organization/project scope from that authorized project, (4) validate a timezone-aware half-open time window (24h default, <=7 days), exact filters and limits, and (5) distinguish valid empty results from dependency failure (`503`). Ensure stable pagination/truncation contracts and backward-compatible field changes when the endpoint is implemented. Querying a foreign existing project must return the same `404` as an unknown project **without opening ClickHouse**. Never expose raw OTLP project credentials via these APIs.

Route names and response field schemas remain **TBD until the M6.1 code and tests establish them**. The authoritative future acceptance matrix is `V1_M6_MILESTONE_TESTING.md`.

## M6.2 browser catalog and detail consumption (implemented)

The frontend calls `GET /api/v1/projects/{project_id}/services/catalog/` with bounded
`start`, `end` and `limit=500`, then calls the distinct `services/detail/` endpoint
for the selected exact service/environment pair. Selection query parameters grant no
project access; every Django read authorizes membership. Metrics/Logs explorer links
are not prefiltered. Observed trace-ID links preserve the project and window.
This implementation has passed automated tests, not yet recorded manual browser acceptance.

## In-app setup and reference links

From project **Settings**, use `/docs/telemetry-setup` to follow a real project API-key OTLP/HTTP Python example or `/docs/api-reference` for control-plane endpoint groups, response codes and limits. Both links render read-only pages inside the authenticated Sentrix UI. The mirrored repository guides are [`docs/PROJECT_TELEMETRY_SETUP.md`](docs/PROJECT_TELEMETRY_SETUP.md) and [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md). These are documentation routes, **not** new `/api/v1/` or `/v1/` endpoints. A project `telemetry:write` key cannot call session-authenticated control-plane APIs.
