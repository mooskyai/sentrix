# Sentrix API reference: authentication, routes and limits

## M6.4 observed service relationships — candidate API

Project members can use `GET /api/v1/projects/{project_id}/services/map/`
with optional RFC3339 `start`, `end` and integer `limit` (default 100; max 500).
Only Django-session-authorized projects are readable. Response has
`project_id`, `start`, `end`, `limit`, `truncated`, `span_scan_truncated`,
`scanned_spans` and `relationships` with observed parent/child service pairs,
environments, counts, and up to three sample trace IDs. Half-open UTC windows
are at most seven days; 10,000 spans are scanned per request. Unobserved or
missing parentage is not a service-health finding. A failure returns 503; a
foreign or unknown project returns 404 without a telemetry read. This route
is an implementation candidate pending operational acceptance.

This document complements the canonical root [API.md](../API.md) and is linked from project **Settings → API reference**. It documents stable implemented routes. No Kubernetes API integration is implied.

## Bases and authentication

| Base | Authentication | Purpose |
| --- | --- | --- |
| `/api/v1/` | Django browser session; CSRF header for mutations; authorized organization/project membership | Control plane and telemetry reads |
| `/v1/` | `Authorization: Bearer sentrix_pk_...`, `telemetry:write` | OTLP/HTTP protobuf telemetry ingestion |

**A project API key is not a control-plane API token.** Creating a key requires a writable organization membership (owner, admin, editor), and the raw secret is returned only in the successful creation response. Store it in a secret manager.

## Authentication and resources

| Method | Route | Description |
| --- | --- | --- |
| GET | `/api/v1/health/live/` | Liveness |
| GET | `/api/v1/health/ready/` | PostgreSQL/Redis/ClickHouse readiness |
| GET | `/api/v1/auth/csrf/` | CSRF token and cookie |
| POST | `/api/v1/auth/login/` | Username/password with CSRF |
| POST | `/api/v1/auth/logout/` | Clear session, 204 |
| GET | `/api/v1/auth/me/` | Current session user |
| GET, POST | `/api/v1/organizations/` | Accessible organizations, create |
| GET, POST | `/api/v1/projects/` | Accessible projects, create |
| GET, POST | `/api/v1/projects/{project_id}/api-keys/` | Project key metadata/list/create (writer only) |
| DELETE | `/api/v1/projects/{project_id}/api-keys/{api_key_id}/` | Revoke project credential |

## OTLP/HTTP ingestion

All require binary protobuf `Content-Type: application/x-protobuf` plus project-key Bearer authentication. Optional `Content-Encoding: gzip` is supported; these paths **never** use trailing slashes.

| Method | Route | Signal |
| --- | --- | --- |
| POST | `/v1/traces` | Resource spans |
| POST | `/v1/metrics` | Metric data points |
| POST | `/v1/logs` | Log records |

`200` acknowledges successful non-empty persistence; common failure codes: `400` invalid protobuf, `401` missing/invalid key, `403` missing scope, `413` too large, `415` unsupported encoding/type, `503` sink failure. The default decompressed limit is 64 MiB (configured via `OTLP_MAX_REQUEST_BYTES`).

## Session-authenticated project telemetry queries

All routes begin `/api/v1/projects/{project_id}/`; `{project_id}` is the authorized project UUID resolved through the current user. A foreign/unknown project responds with a nondisclosing `404` before ClickHouse access.

| GET suffix | Contract |
| --- | --- |
| `services/catalog/` | Default 24h, maximum 7d, `limit=100` default, max 500; exact service/environment counts and first/last observations |
| `services/detail/` | Exact required `service_name` and `environment` (empty environment allowed); bounded metric names, error logs, trace IDs |
| `metrics/catalog/` | Bounded metric discovery |
| `metrics/series/` | Required `metric_name`, optional exact service/environment, scalar points; limit max 5000 |
| `logs/search/` | Exact service/environment, severity 0–24, text substring, 32-hex nonzero trace ID, limit max 1000 |
| `traces/{trace_id}/` | Exact nonzero 32-hex trace identifier; limit max 1000; raw stored spans |

All times use timezone-aware RFC3339 `start` and `end` with a half-open `[start,end)` interval, maximum 7d. Most explorations default to 1h; Services defaults to 24h. Valid empty results are not errors or proof of down services; unavailable telemetry returns `503`.

## Panels, alerts and notifications

| Methods | Suffix after `/api/v1/projects/{project_id}/` |
| --- | --- |
| GET, POST | `dashboard-panels/` (max six panels) |
| DELETE | `dashboard-panels/{panel_id}/` |
| GET, POST | `alert-rules/` (max 50) |
| GET, PATCH, DELETE | `alert-rules/{rule_id}/` |
| GET, POST | `notification-channels/` (max ten) |
| GET, PATCH, DELETE | `notification-channels/{channel_id}/` |
| GET | `notification-deliveries/?limit=100` (max 500) |

Additional alert-state fields, signing headers, authentication nuances, response schemas and worker commands are documented in [API.md](../API.md). See [PROJECT_TELEMETRY_SETUP.md](PROJECT_TELEMETRY_SETUP.md) for a working Python OTLP trace export.
