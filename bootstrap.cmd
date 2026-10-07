@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed or is not on PATH.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Start Docker Desktop and run this script again.
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose v2 is not available.
    exit /b 1
)

if not exist "docker-compose.yml" (
    echo ERROR: docker-compose.yml was not found. Run this script from the Sentrix repository root.
    exit /b 1
)

echo.
echo ==^> Preparing environment
if not exist ".env" (
    if not exist ".env.example" (
        echo ERROR: .env.example was not found.
        exit /b 1
    )
    copy /Y ".env.example" ".env" >nul
    if errorlevel 1 goto :failed
    echo Created .env from .env.example.
) else (
    echo .env already exists; leaving it unchanged.
)

echo.
echo ==^> Validating Docker Compose configuration
docker compose config --quiet
if errorlevel 1 goto :failed

echo.
echo ==^> Starting Sentrix with Docker Compose
docker compose up -d --build
if errorlevel 1 goto :failed

echo.
echo ==^> Waiting for the Django API
set "API_READY="
for /L %%I in (1,1,60) do (
    docker compose exec -T api /opt/venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live/', timeout=2).read()" >nul 2>&1
    if not errorlevel 1 (
        set "API_READY=1"
        goto :api_ready
    )
    timeout /t 2 /nobreak >nul
)

:api_ready
if not defined API_READY (
    docker compose ps
    docker compose logs --tail=120 api
    echo ERROR: The Django API did not become ready within 120 seconds.
    exit /b 1
)

echo.
echo ==^> Applying PostgreSQL migrations
docker compose exec -T api /opt/venv/bin/python manage.py migrate --noinput
if errorlevel 1 goto :failed

echo.
echo ==^> Applying ClickHouse telemetry schema
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema
if errorlevel 1 goto :failed

echo.
echo ==^> Validating ClickHouse telemetry schema
docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
if errorlevel 1 goto :failed

echo.
echo ==^> Running Django system check
docker compose exec -T api /opt/venv/bin/python manage.py check
if errorlevel 1 goto :failed

echo.
echo ==^> Verifying application readiness
docker compose exec -T api /opt/venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready/', timeout=5).read()"
if errorlevel 1 goto :failed

echo.
echo ==^> Ensuring an initial Django admin user exists
docker compose exec -T api /opt/venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; raise SystemExit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)" >nul 2>&1
if not errorlevel 1 (
    echo A Django superuser already exists; skipping user creation.
    goto :user_ready
)

echo No Django superuser exists. Create the initial Sentrix admin user now.
docker compose exec api /opt/venv/bin/python manage.py createsuperuser
if errorlevel 1 goto :failed

:user_ready
echo.
echo ==^> Final service status
docker compose ps

echo.
echo Sentrix initial setup is complete.
echo.
echo Web:        http://localhost:5173
echo Django API: http://localhost:8000
echo Liveness:   http://localhost:8000/api/v1/health/live/
echo Readiness:  http://localhost:8000/api/v1/health/ready/
echo ClickHouse: http://localhost:8123
echo Admin:      http://localhost:8000/admin/
echo.
echo Useful commands:
echo   docker compose ps
echo   docker compose logs -f api
echo   docker compose logs -f web
echo   docker compose down
echo.
echo The bootstrap script preserves existing PostgreSQL and ClickHouse volumes and never uses uv run inside the API container.
exit /b 0

:failed
echo.
echo ERROR: Sentrix bootstrap failed. Review the command output above.
exit /b 1
