# Sentrix V1 M2 — Telemetry Ingestion Testing

## 1. Gate discipline

Each V1 M2 part has its own release gate. Do not start the next part until the current part is green,
committed, and pushed.

## 2. M2.1 — Project API Key Control Plane

### Automated cases

| ID | Scenario | Expected |
| --- | --- | --- |
| KEY-001 | owner creates key | HTTP 201, one-time secret returned |
| KEY-002 | admin creates key | HTTP 201 |
| KEY-003 | editor creates key | HTTP 201 |
| KEY-004 | viewer lists keys | HTTP 403 |
| KEY-005 | viewer creates key | HTTP 403 |
| KEY-006 | viewer revokes key | HTTP 403 |
| KEY-007 | member targets foreign project UUID | HTTP 404/not accessible |
| KEY-008 | list after create | no `secret` or `secret_hash` |
| KEY-009 | persisted key | full token/plain secret not stored |
| KEY-010 | valid future expiry | accepted |
| KEY-011 | past expiry | validation error |
| KEY-012 | revoke | row retained and `revoked_at` populated |

### Backend gate

Run from the repository root:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest
docker compose exec api /opt/venv/bin/ruff check .
docker compose exec api /opt/venv/bin/ruff format --check .
docker compose exec api /opt/venv/bin/mypy .
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
docker compose config --quiet
```

The existing backend suite has 12 tests before M2.1. M2.1 adds eight collected cases, so the expected
count is approximately 20 tests. Exact count is informational; zero failures and the security
assertions above are the release requirement.

### Manual verification

1. Sign in as an owner/admin/editor.
2. Create a key for an accessible project.
3. Copy the returned `secret` and confirm it appears only in that create response.
4. List keys and confirm only metadata is returned.
5. Revoke the key and confirm the row remains listed with `revoked_at`.
6. Sign in as a viewer and confirm list/create/revoke are denied.
7. Attempt an exact foreign project UUID and confirm it is inaccessible.

## 3. Stop condition

After M2.1 passes, commit and push it. Only then may M2.2 machine authentication be designed or
patched.
