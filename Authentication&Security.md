# Sentrix — Authentication, Authorization and Security

## Framework onboarding credential boundary

The authenticated Documentation page is globally accessible but does not retrieve secrets.
A project key is disclosed once via writable project Settings, and authorizes only
OTLP/HTTP protobuf ingestion with `telemetry:write`. Laravel, Node.js and Next.js
examples hold credentials in server-only environment/secrets. Vite `VITE_*` and
Next `NEXT_PUBLIC_*` variables are public and must never contain project keys.
No browser-to-Sentrix secret proxy or client-side OTLP authentication is added.

## M6.3 Infrastructure — implementation candidate (not accepted)

M6.3 Infrastructure reads require authenticated Django session + `projects_for_user` before
ClickHouse. Each metrics/logs/spans branch scopes by server-derived organization and project
UUIDs; client-supplied resource keys never authorize access. Supported keys are server
allowlisted, and queries use typed timestamps/UUIDs and bounded limits. Unknown/foreign UUIDs
return 404 without opening a ClickHouse client. Query failure is a generic 503; suppress raw
exception strings. No Kubernetes credentials/API boundary exists.

## Synthetic demo seeding trust boundary

The opt-in `seed_demo --username` command requires an existing active Django user,
creates only that user's reserved demo organizations/projects, refuses slug collisions
with different owners, sends OTLP through temporary authorized project keys and deletes
the keys in `finally`. Only a revoked demonstration key remains visible in the UI.
The demo webhook channel is disabled, and the command never prints secret values.
Synthetic fixture membership is not a foreign-user authorization proof.

## M6.1 catalog read boundary

Session authentication and Django project membership precede ClickHouse client creation. A route UUID,
service name, environment string, and any OTLP resource attribute are untrusted identifiers, not tenant
authority. Every participating signal query must use the authorized project's own organization and
project UUIDs. Foreign and nonexistent projects are nondisclosing `404` responses. Queries are time/
cardinality bounded; invalid parameters are `400`; ClickHouse outages are generic `503` without
credentials, raw SQL, or exception strings in responses. No catalog write roles or machine-key reads.

**Status:** V1 M1–M5 implemented boundaries. This document describes current controls and known constraints; it is not an external security certification.

## 1. Trust boundaries

```text
Browser -> Django session cookie + CSRF -> membership-scoped control-plane/API
Collector/SDK -> project Bearer key + telemetry:write -> OTLP/HTTP sink
Django authorized telemetry query -> typed tenant predicates -> ClickHouse
Alert evaluator -> PostgreSQL state transition -> durable delivery -> egress-policy webhook
```

Browser session and machine key are distinct, never interchangeable.

## 2. Session authentication

- Login at `POST /api/v1/auth/login/` after `GET /api/v1/auth/csrf/`; Django password hashing and session cookies.
- REST framework defaults to `SessionAuthentication` and authenticated permissions for domain APIs.
- State-changing browser requests carry `X-CSRFToken`; logout invalidates session; session cookie is HttpOnly with Lax SameSite.
- Production (`DJANGO_DEBUG=false`) sets secure session and CSRF cookies. Host/origin/CSRF allowlists must be configured for actual deployment topology.
- Public self-registration, OAuth/OIDC/SAML, MFA, and password-reset UI are **not part of implemented M1–M5**.

## 3. Tenant membership and RBAC

Every project belongs to an organization; membership role is `owner`, `admin`, `editor`, or `viewer`. Organization creation grants creator owner membership. Django resolves projects from `projects_for_user(user)` first; children load with both project and resource UUID. Known foreign UUID, name, or trace ID cannot bypass membership checks. Viewers may read permitted telemetry/rules/state but cannot change credential/panel/rule/channel config. Organization updates require owner/admin.

Write-control hiding in React is convenience, not authorization. Every new endpoint needs tests for anonymous, viewer, writable, unknown and **real foreign** project.

## 4. Project machine API keys

- `ProjectApiKey` stores a unique public prefix plus Django-hashed secret, JSON scopes, optional expiry/revocation and last-used timestamp.
- Raw key is returned only during project credential creation, never from list/detail APIs or query caches. Revoke or recreate if lost.
- OTLP endpoints require `Authorization: Bearer sentrix_pk_...` and scope `telemetry:write`; invalid/revoked/expired keys fail generically.
- The verified database relationship, not caller IDs or OTel attributes, supplies `organization_id` + `project_id` for ClickHouse writes.
- Never place secrets in a command argument, repository, screenshot, log, URL query, or persisted developer diagnostic.

## 5. Telemetry security

- `POST /v1/metrics|logs|traces`: authenticated before protobuf decoding; only `application/x-protobuf`, identity/gzip, bounded decompressed bytes.
- Query APIs resolve authorized project before creating ClickHouse client. Each read uses both tenant UUIDs with typed params and server-enforced limits.
- Unknown/foreign projects yield nondisclosing 404; ClickHouse outages yield 503. No raw tenant-wide query available to browser.
- Trace IDs and metric/log attributes are **data**, never authority or executable query instructions.

## 6. Webhook egress and signing

- Channel endpoints are write-only, list/detail return redacted host/scheme display. Creation returns one signing secret derived via HMAC from deployment `DJANGO_SECRET_KEY` and channel UUID; plaintext secret is not stored as a channel column.
- Production host allowlist defaults **empty** in Django settings, HTTP disabled unless explicitly configured. Compose defaults are **local-development overrides**, not production-ready.
- Reject URL userinfo, fragments, query strings, unapproved hostname, disallowed scheme. Redirects are blocked.
- Payload is canonical JSON; `X-Sentrix-Timestamp` + `.` + body signed with `X-Sentrix-Signature: sha256=<hex>`. Receivers should validate timestamp tolerance, match correct signing secret, compare signatures in constant time, and deduplicate `X-Sentrix-Delivery`.
- Outbound HTTP occurs only in one-shot dispatcher after row claim; at most 3 attempts with 1m/5m retry intervals, bounded leases and status codes. No arbitrary response body/error string persistence.
- **Residual consideration:** exact hostname allowlisting alone is not full DNS/IP SSRF pinning; deploy network-layer egress controls and review DNS/rebinding exposure before accepting public/untrusted destinations. Derived-secret rotation follows `DJANGO_SECRET_KEY` rotation.

## 7. Sensitive state and operating rules

Minimize privilege for Postgres/ClickHouse credentials; use HTTPS outside local development; store production secrets in a secret manager; protect backups and logs; rotate API keys/signing keys according to defined process; do not treat locally open Compose ports as production hardening. Do not use `down -v` for regular cleanup. Report suspected tenant-crossing or credential disclosure as a release blocker.

## 8. Security regression checklist

Anonymous denial; real foreign project 404 before DB query; read-only viewer mutation 403; one-time secret redaction; expired/revoked key denial; gzip/body size errors; parameterized data-plane filters; scoped delivery; HMAC correctness; retry/lease/stale completion; webhook allowlist and 3xx deny. Update this file alongside security-sensitive changes and link tests in `Testing&QA.md`.

## 8. M6-specific tenant and inference threat model (planned)

Service names, environments, span IDs and OTel resource attributes are **untrusted observation fields**, not authorization credentials. Future discovery, resource and graph queries must authorize the project via a browser session and membership first; only server-derived project/organization IDs may scope ClickHouse. Every nested lookup/join must constrain both IDs **and trace identity** where applicable. A foreign existing project and a random project ID must be indistinguishable `404`s before any ClickHouse access.

Keep M6 list/detail queries bounded and typed. Do not leak metadata from neighboring tenants via counts, completions, suggestions, graph edges, absent-resource error differences or shared cache keys. Resource tags can contain sensitive infrastructure strings: return only fields required for the implemented view and never reinterpret arbitrary attributes as secrets or service ownership. Do not infer security posture, service health, operational readiness, Kubernetes API reachability or network topology from incomplete telemetry. No additional Kubernetes credential/storage trust boundary is approved for M6.

## Documentation link trust boundary

Authenticated read-only documentation routes under `/docs/` are static guides, not API endpoints or authorizing capabilities. Project Settings must show no raw key in the documentation URLs, query strings or page state; the existing one-time credential UI remains the only way to see a newly created secret. The docs clearly separate `telemetry:write` machine bearer keys for `/v1/{metrics,logs,traces}` from Django session + CSRF protected `/api/v1/` operations. Viewers may read the guides but cannot query API-key metadata or create/revoke keys.
