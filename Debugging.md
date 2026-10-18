# Sentrix — Debugging and Incident Diagnosis

**Scope:** supported V1 M1–M5 local development and operational tests. Preserve PostgreSQL/ClickHouse volumes and never leak secrets while collecting evidence.

## 1. Establish the exact state

```powershell
git status -sb
git rev-parse HEAD
git diff --check
docker compose config --quiet
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 clickhouse
```

Compare the expected baseline and the actual user terminal output before changing any code. Never `git apply --3way`, force-apply, or blindly reset the worktree to make errors disappear.

## 2. Dependency/readiness failures

- `GET http://localhost:8000/api/v1/health/live/` checks API process, **not** downstream dependencies.
- `/api/v1/health/ready/` checks PostgreSQL, Redis and ClickHouse; HTTP 503 means dependency unavailable.
- For DB migrations: `docker compose exec -T api /opt/venv/bin/python manage.py migrate --noinput`.
- For telemetry table mismatch: `docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check`. Repair via the explicit schema command only when consistent with tracked `clickhouse_schema.py`; no manual ad hoc destructive DDL.
- For build drift, verify the mounted source is current with `docker compose up -d --build --force-recreate`; this preserves volumes. **Never** `docker compose down -v`.

## 3. Authentication and tenant issues

- Browser 401/403: check session cookie, `GET /api/v1/auth/csrf/`, login CSRF header, role/membership. Do not paste cookies or passwords.
- OTLP 401: invalid/missing/revoked/expired `sentrix_pk_` key; OTLP 403: verified key missing `telemetry:write`. Never print raw key to debug.
- Foreign or unknown project 404 is **intentional nondisclosure**. Confirm via DB membership with an authorized admin diagnostic; do not weaken selectors to reveal presence.
- A 503 on metrics/logs/traces is dependency failure, **not** healthy no-data.

## 4. OTLP and telemetry query symptoms

| Symptom | Checks |
| --- | --- |
| OTLP 400 | protobuf validity, gzip/body decoding, correct signal type |
| OTLP 413 | configured decompressed `OTLP_MAX_REQUEST_BYTES` |
| OTLP 415 | `application/x-protobuf`, supported content encoding identity/gzip |
| OTLP 503 | sink connectivity / ClickHouse schema / durability; retry with exporter policy |
| No metric in catalog | check exact time window, metric, tenant, resource service/env and ingestion timestamp |
| No scalar series | histogram/summary is not scalar `number_value`; inspect metric type |
| No log | search boundaries, exact severity/service/env, body substring, all-zero IDs normalized to null |
| No trace | exact nonzero 32-hex ID and bounded `[start,end)` covering span times |
| Wrong viewer data | check project UUID in React Query key, component remount and Django membership predicate |

Scope ClickHouse diagnostics by authenticated project identity + bounded timestamp. Never run unscoped telemetry scans as verification.

## 5. Alerts and webhook symptoms

- `pending` until `evaluate_alerts` runs; opening/refreshing Alerts is **not** evaluation.
- `no_data`: no scalar point in rule window. `error`: ambiguous newest point, nonfinite value or ClickHouse failure; inspect **bounded error_code**, not leaked exception text.
- `firing` with no webhook: verify enabled channel, whether a **transition** occurred, then run `dispatch_notifications`. Repeated `firing` intentionally queues nothing.
- `firing -> ok` queues recovery; `firing -> no_data/error` and disabling do **not** fabricate recovery.
- Channel request denied: inspect exact `NOTIFICATION_WEBHOOK_ALLOWED_HOSTS`, scheme and HTTP toggle. Production defaults deny without allowlist; localhost Compose overrides are dev-only.
- Delivery `retry`: check attempt_count, next_attempt_at (1m then 5m); terminal `failed` after 3 attempts or a nonretryable status. Dispatcher intentionally returns nonzero when its run processes terminal failure.
- HMAC mismatch: check exact raw JSON bytes (do not reserialize), UTF-8 secret, timestamp followed by dot, and correct channel's one-time signing secret.
- Expired lease can be reclaimed; stale completion must not overwrite another claim. Review `apps/alerts/notifications.py`, don't mutate production delivery records manually.

## 6. Windows/PowerShell pitfalls

- `git diff --stat` does not list untracked new files; after `git add`, inspect `git diff --cached --stat`.
- Use `git apply --check` before `git apply`; if it fails, stop and rebaseline rather than force.
- `Invoke-RestMethod` array handling can surprise on 1-vs-2 item JSON arrays; for stable counts use `Invoke-WebRequest` content parsed through `ConvertFrom-Json` and assert array shape.
- A local Python process can lock `backend/.venv/Scripts/python.exe`; stop **only** that receiver/process before removing a temporary venv. Do not kill unrelated Python processes.
- Ignore generated `frontend/*.tsbuildinfo` and local `.venv` directories; never stage build artifacts.

## 7. Escalation and recovery

1. Capture exact error, command, SHA, environment, affected project (safe UUID only) and minimal sanitized logs.
2. Reproduce via targeted failing test/smoke; isolate whether bug is application, environment, verifier, or test expectation.
3. Correct smallest relevant layer, add regression, update impacted docs and `ProjectImplementation.md`.
4. Rerun focused gate and relevant operational acceptance; commit only after green. For migrations, design rollback before touching live data.

## 8. Planned M6 discovery/resource/relationship diagnosis

M6 query code is not yet implemented. When it exists, debug missing services with exact observed `(service_name, environment)`, project UUID authorized through session membership, `start/end` UTC window, and signal-specific timestamps. Inspect ClickHouse with **both** tenant IDs; never use unscoped exploratory SQL as verification. An unobserved service within the interval is not automatically down. A `503` means dependency failure, not no service.

For infrastructure, check which exact OpenTelemetry semantic convention keys were present on *the same supporting resource/telemetry row* before claiming a host/cluster/workload/pod association. For dependency edges, confirm actual child `parent_span_id`, parent `span_id`, matching `trace_id`, project and differing service identities; span links or nearby timestamps do not prove parentage. Keep sensitive resource attributes and project keys out of logs and bug reports. Update this troubleshooting section with verified failure signatures when M6.1–M6.5 are implemented.
