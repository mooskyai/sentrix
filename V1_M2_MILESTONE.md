# Sentrix V1 M2 — Telemetry Ingestion Foundation

## 1. Goal

V1 M2 establishes the first trustworthy telemetry data path for Sentrix. It starts with project-scoped
machine credentials, then adds machine authentication, OTLP/HTTP ingestion, ClickHouse telemetry
schemas, end-to-end persistence, credential management UI, and operational verification.

M2 is intentionally split into independently testable parts. A part is not started until the previous
part is green, committed, and pushed.

## 2. Part sequence

1. **M2.1 — Project API Key Control Plane**
2. **M2.2 — Machine Authentication Boundary**
3. **M2.3 — OTLP/HTTP Ingestion Gateway**
4. **M2.4 — ClickHouse Telemetry Schema**
5. **M2.5 — End-to-End OTLP to ClickHouse**
6. **M2.6 — API Key Management UI**
7. **M2.7 — Operational Verification and Documentation**

## 3. M2.1 scope

M2.1 introduces project-scoped machine credentials only. It does not authenticate ingestion requests
yet and does not accept or store telemetry.

A project API key stores:

```text
id
project_id
name
prefix
secret_hash
scopes
created_by
expires_at
last_used_at
revoked_at
created_at
updated_at
```

The initial scope is intentionally limited to:

```text
telemetry:write
```

The raw key format is:

```text
sentrix_pk_<public-prefix>_<secret>
```

Only the public prefix and a one-way password hash of the secret are persisted. The full credential is
returned exactly once from the create endpoint and must never appear in list responses, logs, or
database plaintext.

## 4. M2.1 API

```text
GET    /api/v1/projects/{project_id}/api-keys/
POST   /api/v1/projects/{project_id}/api-keys/
DELETE /api/v1/projects/{project_id}/api-keys/{api_key_id}/
```

`DELETE` is a revoke operation. It sets `revoked_at`; it does not delete the database row.

## 5. M2.1 authorization

Only organization roles that already have project write authority may manage project API keys:

```text
OWNER   allowed
ADMIN   allowed
EDITOR  allowed
VIEWER  denied
```

Project lookup remains membership-scoped. A caller cannot use an exact foreign project UUID to create,
list, or revoke API keys.

## 6. M2.1 acceptance

M2.1 is green only when:

- the schema migration is present and `makemigrations --check --dry-run` reports no drift;
- owner/admin/editor can create keys;
- viewer management requests are denied;
- foreign project access returns not found/denied without changing foreign state;
- the generated secret is returned only on create;
- plaintext credentials are not persisted;
- list responses expose neither `secret` nor `secret_hash`;
- expiry must be in the future when provided;
- revoke retains metadata and sets `revoked_at`;
- Ruff, Ruff formatting, mypy, Django checks, pytest, and Compose configuration pass.

## 7. Explicitly out of scope for M2.1

- bearer-token authentication of ingestion traffic;
- `last_used_at` updates from machine authentication;
- OTLP protocol endpoints;
- metrics/logs/traces parsing;
- ClickHouse telemetry tables;
- telemetry UI;
- API key management UI.

Those belong to later M2 parts and must not be pulled forward before M2.1 is accepted.


## 8. M2.2 — Machine Authentication Boundary

M2.2 makes the M2.1 project API keys usable as machine credentials. It introduces a dedicated DRF
authenticator and scope permission without registering machine credentials globally or creating an
OTLP endpoint.

Authentication flow:

```text
Authorization: Bearer sentrix_pk_<prefix>_<secret>
                    |
                    v
          parse public prefix
                    |
                    v
          load ProjectApiKey
                    |
                    v
       verify one-way secret hash
                    |
          revoked / expiry check
                    |
                    v
       ProjectApiKeyPrincipal
 organization_id / project_id / api_key_id / scopes
                    |
                    v
          endpoint scope check
```

A successful authentication updates `last_used_at` and returns the persisted API-key object as
`request.auth`. The principal is the sole source of tenant/project identity for future machine
endpoints.

## 9. M2.2 acceptance

M2.2 is green only when:

- a valid Bearer key authenticates and exposes the correct organization/project/key IDs and scopes;
- `last_used_at` advances after successful credential authentication;
- wrong-secret, unknown, revoked, expired, and malformed credentials are rejected;
- failed credential authentication does not update `last_used_at`;
- a valid key missing an endpoint-required scope receives HTTP 403;
- a browser/session user without a project Bearer key cannot pass a machine-only endpoint;
- machine authentication is not added to the global DRF authentication classes;
- no schema migration is introduced by M2.2;
- Ruff, Ruff formatting, mypy, Django checks, pytest, frontend regressions, and Compose validation pass.

## 10. Explicitly out of scope for M2.2

- `/v1/metrics`, `/v1/logs`, or `/v1/traces` routes;
- OTLP protobuf or JSON decoding;
- request-body limits for telemetry payloads;
- ClickHouse telemetry schemas or writes;
- streaming/queue infrastructure;
- API-key management UI.

Those capabilities remain ordered behind M2.2. M2.3 begins only after this part is green, committed,
and pushed.

## 11. M2.3 — OTLP/HTTP Ingestion Gateway

M2.3 establishes the real OTLP/HTTP protocol boundary while intentionally stopping before durable
telemetry storage. The standard signal routes are:

```text
POST /v1/metrics
POST /v1/logs
POST /v1/traces
```

All three routes require a valid project API key containing `telemetry:write`. The API-key principal is
the only source of organization/project/key identity. Requests initially use binary protobuf
(`application/x-protobuf`) and may be uncompressed or gzip-compressed.

The decoder produces a common `OtlpBatch` envelope containing the authenticated tenant context, signal,
and official decoded OTLP request message. The sink boundary is deliberately separate from protocol
decoding. Until durable persistence is wired, non-empty batches return retryable HTTP 503 instead of a
false success response.

## 12. M2.3 acceptance

M2.3 is green only when:

- `/v1/metrics`, `/v1/logs`, and `/v1/traces` accept valid binary OTLP protobuf through a test sink;
- every decoded batch carries organization/project/API-key IDs derived from the credential;
- missing credentials return 401 and missing `telemetry:write` returns 403;
- malformed protobuf returns 400;
- oversized bodies return 413;
- unsupported media types/content encodings return 415;
- gzip payloads are decoded with the size limit rechecked after decompression;
- protocol errors for binary requests use `google.rpc.Status`;
- non-empty telemetry is not acknowledged while durable persistence is unavailable;
- empty OTLP requests may return the correct empty Export*ServiceResponse;
- no Django model or telemetry migration is introduced;
- the dependency lock is refreshed after adding the official protobuf packages;
- backend/frontend/infrastructure quality gates remain green.

## 13. Explicitly out of scope for M2.3

- OTLP/JSON decoding;
- ClickHouse metrics/log/span schemas;
- durable telemetry writes;
- query APIs/explorers;
- streaming/queue infrastructure;
- API-key management UI.

M2.4 may begin only after M2.3 is green, committed, and pushed.
