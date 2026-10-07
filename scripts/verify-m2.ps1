$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not on PATH."
    }

    Write-Host "== Docker Compose =="
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration validation failed." }

    $runningServices = @(docker compose ps --services --status running)
    if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Docker Compose services." }
    $requiredServices = @("postgres", "redis", "clickhouse", "api", "web")
    $missingServices = @($requiredServices | Where-Object { $_ -notin $runningServices })
    if ($missingServices.Count -gt 0) {
        throw "Required Compose services are not running: $($missingServices -join ', ')."
    }

    Write-Host "== Health =="
    $null = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 10
    $null = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health/live/" -TimeoutSec 10
    $null = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health/ready/" -TimeoutSec 10

    Write-Host "== ClickHouse schema =="
    docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
    if ($LASTEXITCODE -ne 0) { throw "ClickHouse schema validation failed." }

    $apiKey = $env:SENTRIX_OTLP_API_KEY
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        $secureApiKey = Read-Host "Project telemetry API key" -AsSecureString
        $apiKey = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
    }
    if ([string]::IsNullOrWhiteSpace($apiKey) -or -not $apiKey.StartsWith("sentrix_pk_")) {
        throw "A valid Sentrix project API key is required."
    }

    Write-Host "== Real OTLP/HTTP trace export =="
    $apiKey | docker compose exec -T -e PYTHONPATH=/app api /opt/venv/bin/python scripts/otlp_trace_smoke.py
    if ($LASTEXITCODE -ne 0) { throw "OTLP operational smoke verification failed." }

    Write-Host "M2 operational verification passed."
}
finally {
    $apiKey = $null
    Pop-Location
}
