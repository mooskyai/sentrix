$ErrorActionPreference = "Stop"

Write-Host "== Docker Compose =="
docker compose config --quiet

Write-Host "== Backend =="
Push-Location backend
try {
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy .
    uv run python manage.py check
    uv run python manage.py makemigrations --check --dry-run
    uv run pytest -q
}
finally {
    Pop-Location
}

Write-Host "== Frontend =="
Push-Location frontend
try {
    npm run lint
    npm run typecheck
    npm run test
    npm run build
}
finally {
    Pop-Location
}

Write-Host "All verification commands passed."
