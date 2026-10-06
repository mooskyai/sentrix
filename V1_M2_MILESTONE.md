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
