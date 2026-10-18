# Sentrix — Setup and Developer Environment

**Acceptance target:** Windows 11 + PowerShell 7 + Docker Desktop / Compose v2. Linux/macOS bootstrap supported via `bootstrap.sh`. Use the checked-in `.env.example` and actual Compose config as environment authority.

## 1. Stack and prerequisites

- Docker Desktop with Compose v2 running, Git, sufficient resources for PostgreSQL 18, Redis 8, ClickHouse 25.8, Django API, Vite web.
- Backend: Python >=3.14,<3.15 via uv (`backend/pyproject.toml`); Docker image uses `python:3.14-slim`.
- Frontend: Node >=24 for local use; Compose image `node:24-alpine`; React 19 / TypeScript / Vite 8 / Tailwind 4.
- Native `uv` and Node are **optional for normal Compose bootstrap**, useful for host development.

## 2. First launch from repository root

```powershell
git status -sb
Copy-Item .env.example .env  # only if .env does not exist
.\bootstrap.cmd
```

On bash: `./bootstrap.sh`. Bootstrap validates Docker, preserves existing `.env`, starts Compose, waits for API, applies Django migrations and ClickHouse schema, validates readiness, creates a Django superuser **only if needed**, then prints URLs.

| Service | Local address |
| --- | --- |
| React Vite | `http://localhost:5173` |
| Django API | `http://localhost:8000` |
| Django admin | `http://localhost:8000/admin/` |
| liveness / readiness | `/api/v1/health/live/`, `/api/v1/health/ready/` |
| ClickHouse HTTP | `http://localhost:8123` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

## 3. Compose operations

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f api
docker compose logs -f web
docker compose down  # preserves volumes
```

**Never run `docker compose down -v`** in normal development, release gates or debugging; it destroys persisted Postgres/ClickHouse volumes.

## 4. Environment configuration

Configure `.env` from `.env.example` before production use: rotate `DJANGO_SECRET_KEY`, disable debug, configure allowed hosts/CORS/CSRF, set database credentials, provision restricted ClickHouse users and HTTPS network ingress. `OTLP_MAX_REQUEST_BYTES` defaults to `67108864`. Webhook configuration: `NOTIFICATION_WEBHOOK_ALLOWED_HOSTS` (exact hostnames), `NOTIFICATION_WEBHOOK_ALLOW_HTTP` (development only), `NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS`. The Compose file explicitly defaults to local development settings; **do not deploy Compose defaults as production security settings**.

`.env` is local and must never contain committed credentials. Keep project API keys and webhook signing secrets out of environment screenshots/terminal history wherever possible.

## 5. Manual schema and readiness

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py migrate --noinput
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
docker compose exec -T api /opt/venv/bin/python manage.py check
```

## 6. Local host development (alternative)

Start backing services with `docker compose up -d postgres redis clickhouse`. Set `POSTGRES_HOST=localhost`, `CLICKHOUSE_HOST=localhost`, Redis localhost for host Django; compose-container DNS names (`postgres`, `clickhouse`) will not resolve on the host. In `backend/` run `uv sync --group dev`, `uv run python manage.py migrate`, `uv run python manage.py runserver`; in `frontend/` run `npm install`, `npm run dev`. Keep these environments distinct from the API image's `/opt/venv`.

## 7. Verify a development slice

```powershell
.\scripts\verify.ps1
# operational tests require interactive session/real telemetry:
.\scripts\verify-m2.ps1
.\scripts\verify-m3.ps1
.\scripts\verify-m4.ps1
.\scripts\verify-m5.ps1
```

`verify.ps1` runs pytest, Ruff/mypy, Django/migration/ClickHouse schema checks, frontend lint/typecheck/tests/build and repo whitespace check. Operational scripts may rebuild/recreate containers without deleting volumes; do not run all interactive smoke scripts on every tiny change unless required by active milestone.

## 8. Updates and onboarding

When changing runtime versions, dependency locks, variables, ports, bootstrap, or command locations, update `Setup.md`, `README.md`, `AGENTS.md` if workflow changed, `.env.example`, and milestone acceptance in the same patch.

## 8. Version-1 milestone setup and M6 readiness

The same documented Docker/Python/Node stack supports **implemented V1 M1–M5**. M6's planned service/resource discovery should reuse the existing project-scoped OTLP ingestion and ClickHouse schema; **do not add Kubernetes credentials, Kubernetes API clients, graph services, or inventory databases** simply to prepare for M6. Use the current `docker-compose.yml` and `.env.example` as the actual runtime configuration, not a new speculative environment file.

Before each M6 slice: verify a clean `main`, run `docker compose config --quiet`, confirm liveness/readiness and `manage.py clickhouse_schema --check`, and apply the exact verified patch. M6.5 should introduce its own verified operational command only when code is ready; `scripts/verify-m6.ps1` is **planned, not present** at M5 closeout. Continue using `scripts/verify.ps1` as the mandatory full release gate in the meantime.
