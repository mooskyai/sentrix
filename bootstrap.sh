#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf '\nERROR: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or is not on PATH."
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker and run this script again."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not available."

[[ -f docker-compose.yml ]] || fail "docker-compose.yml was not found. Run this script from the Sentrix repository root."

log "Preparing environment"
if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || fail ".env.example was not found."
  cp .env.example .env
  echo "Created .env from .env.example."
else
  echo ".env already exists; leaving it unchanged."
fi

log "Validating Docker Compose configuration"
docker compose config --quiet

log "Starting Sentrix with Docker Compose"
docker compose up -d --build

log "Waiting for the Django API"
api_ready=0
for ((attempt = 1; attempt <= 60; attempt++)); do
  if docker compose exec -T api /opt/venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live/', timeout=2).read()" >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 2
done

if [[ "$api_ready" -ne 1 ]]; then
  docker compose ps || true
  docker compose logs --tail=120 api || true
  fail "The Django API did not become ready within 120 seconds."
fi

log "Applying PostgreSQL migrations"
docker compose exec -T api /opt/venv/bin/python manage.py migrate --noinput

log "Applying ClickHouse telemetry schema"
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema

log "Validating ClickHouse telemetry schema"
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check

log "Running Django system check"
docker compose exec -T api /opt/venv/bin/python manage.py check

log "Verifying application readiness"
docker compose exec -T api /opt/venv/bin/python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready/', timeout=5).read()"

log "Ensuring an initial Django admin user exists"
if docker compose exec -T api /opt/venv/bin/python manage.py shell -c \
  'from django.contrib.auth import get_user_model; raise SystemExit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)'; then
  echo "A Django superuser already exists; skipping user creation."
else
  if [[ ! -t 0 ]]; then
    fail "No Django superuser exists and bootstrap is not attached to an interactive terminal. Run ./bootstrap.sh from a terminal to create the initial admin user."
  fi
  echo "No Django superuser exists. Create the initial Sentrix admin user now."
  docker compose exec api /opt/venv/bin/python manage.py createsuperuser
fi

log "Final service status"
docker compose ps

cat <<'DONE'

Sentrix initial setup is complete.

Web:        http://localhost:5173
Django API: http://localhost:8000
Liveness:   http://localhost:8000/api/v1/health/live/
Readiness:  http://localhost:8000/api/v1/health/ready/
ClickHouse: http://localhost:8123
Admin:      http://localhost:8000/admin/

Useful commands:
  docker compose ps
  docker compose logs -f api
  docker compose logs -f web
  docker compose down

The bootstrap script preserves existing PostgreSQL and ClickHouse volumes and never uses `uv run`
inside the API container.
DONE
