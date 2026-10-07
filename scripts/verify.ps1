$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "== Docker Compose =="
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration validation failed." }

    Write-Host "== Backend =="
    docker compose exec -T api /opt/venv/bin/python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
    docker compose exec -T api /opt/venv/bin/ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed." }
    docker compose exec -T api /opt/venv/bin/ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed." }
    docker compose exec -T api /opt/venv/bin/mypy .
    if ($LASTEXITCODE -ne 0) { throw "mypy failed." }
    docker compose exec -T api /opt/venv/bin/python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    docker compose exec -T api /opt/venv/bin/python manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw "Django migration drift check failed." }
    docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
    if ($LASTEXITCODE -ne 0) { throw "ClickHouse schema validation failed." }

    Write-Host "== Frontend =="
    docker compose exec -T web npm run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    docker compose exec -T web npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed." }
    docker compose exec -T web npm test -- --run
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
    docker compose exec -T web npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

    Write-Host "== Repository =="
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }

    Write-Host "All release-gate commands passed."
}
finally {
    Pop-Location
}
