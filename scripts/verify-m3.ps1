param(
    [switch]$SkipComposeRecreate,
    [switch]$SkipReleaseGate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiBase = "http://localhost:8000/api/v1"
$webBase = "http://localhost:5173"
$requiredServices = @("postgres", "redis", "clickhouse", "api", "web")
$panelId = $null
$session = $null
$apiKey = $null
$browserPassword = $null
$smoke = $null

function Assert-ExitCode([string]$message) {
    if ($LASTEXITCODE -ne 0) { throw $message }
}

function Wait-HttpReady([string]$uri, [int]$timeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $uri -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return }
        }
        catch {
            if ((Get-Date) -ge $deadline) { throw "Timed out waiting for $uri." }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $uri."
}

function Get-CsrfHeader($webSession) {
    $cookies = $webSession.Cookies.GetCookies([Uri]"http://localhost:8000")
    $csrfCookie = $cookies["csrftoken"]
    if ($null -eq $csrfCookie -or [string]::IsNullOrWhiteSpace($csrfCookie.Value)) {
        throw "The authenticated session does not contain a CSRF cookie."
    }
    return @{ "X-CSRFToken" = $csrfCookie.Value }
}

function Escape-QueryValue([object]$value) {
    if ($value -is [DateTime]) {
        $value = $value.ToUniversalTime().ToString(
            "o",
            [Globalization.CultureInfo]::InvariantCulture
        )
    }
    elseif ($value -is [DateTimeOffset]) {
        $value = $value.ToUniversalTime().ToString(
            "o",
            [Globalization.CultureInfo]::InvariantCulture
        )
    }
    return [Uri]::EscapeDataString([string]$value)
}

Push-Location $repoRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not on PATH."
    }

    Write-Host "== M3 Compose stack =="
    docker compose config --quiet
    Assert-ExitCode "Docker Compose configuration validation failed."

    if (-not $SkipComposeRecreate) {
        Write-Host "Recreating services from the current repository without deleting persistent volumes..."
        docker compose up -d --build --force-recreate
        Assert-ExitCode "Docker Compose recreation failed."
    }

    $deadline = (Get-Date).AddSeconds(90)
    do {
        $runningServices = @(docker compose ps --services --status running)
        Assert-ExitCode "Unable to inspect Docker Compose services."
        $missingServices = @($requiredServices | Where-Object { $_ -notin $runningServices })
        if ($missingServices.Count -eq 0) { break }
        if ((Get-Date) -ge $deadline) {
            throw "Required Compose services are not running: $($missingServices -join ', ')."
        }
        Start-Sleep -Seconds 2
    } while ($true)

    Write-Host "== Health and schema =="
    Wait-HttpReady "$webBase/"
    Wait-HttpReady "$apiBase/health/live/"
    Wait-HttpReady "$apiBase/health/ready/"
    docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check
    Assert-ExitCode "ClickHouse schema validation failed."

    $apiKey = $env:SENTRIX_OTLP_API_KEY
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        $secureApiKey = Read-Host "Project telemetry API key" -AsSecureString
        $apiKey = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
        $secureApiKey = $null
    }
    if ([string]::IsNullOrWhiteSpace($apiKey) -or -not $apiKey.StartsWith("sentrix_pk_")) {
        throw "A valid Sentrix project API key is required."
    }

    Write-Host "== Real OTLP/HTTP metric export =="
    $smokeOutput = @(
        $apiKey | docker compose exec -T -e PYTHONPATH=/app api `
            /opt/venv/bin/python scripts/otlp_metric_smoke.py
    )
    Assert-ExitCode "OTLP metric operational smoke failed."
    if ($smokeOutput.Count -lt 1) { throw "Metric smoke did not return verification metadata." }
    try {
        $smoke = $smokeOutput[-1] | ConvertFrom-Json
    }
    catch {
        throw "Metric smoke returned invalid verification metadata."
    }

    Write-Host "Verified durable metric $($smoke.metric_name) for project $($smoke.project_id)."

    Write-Host "== Session-authenticated metrics query =="
    $browserUsername = $env:SENTRIX_BROWSER_USERNAME
    if ([string]::IsNullOrWhiteSpace($browserUsername)) {
        $browserUsername = Read-Host "Browser/session username"
    }
    if ([string]::IsNullOrWhiteSpace($browserUsername)) {
        throw "A browser/session username is required."
    }
    $secureBrowserPassword = Read-Host "Browser/session password" -AsSecureString
    $browserPassword = [System.Net.NetworkCredential]::new("", $secureBrowserPassword).Password
    $secureBrowserPassword = $null
    if ([string]::IsNullOrWhiteSpace($browserPassword)) {
        throw "A browser/session password is required."
    }

    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $csrf = Invoke-RestMethod -Uri "$apiBase/auth/csrf/" -WebSession $session -TimeoutSec 10
    $loginBody = @{
        username = $browserUsername
        password = $browserPassword
    } | ConvertTo-Json -Compress
    $null = Invoke-RestMethod `
        -Uri "$apiBase/auth/login/" `
        -Method Post `
        -WebSession $session `
        -Headers @{ "X-CSRFToken" = $csrf.csrfToken } `
        -ContentType "application/json" `
        -Body $loginBody `
        -TimeoutSec 10

    $organizations = @(Invoke-RestMethod -Uri "$apiBase/organizations/" -WebSession $session)
    $projects = @(Invoke-RestMethod -Uri "$apiBase/projects/" -WebSession $session)
    $project = @($projects | Where-Object { [string]$_.id -eq [string]$smoke.project_id }) | Select-Object -First 1
    if ($null -eq $project) {
        throw "The browser/session user cannot access the project bound to the supplied telemetry key."
    }
    $organization = @(
        $organizations | Where-Object { [string]$_.id -eq [string]$project.organization_id }
    ) | Select-Object -First 1
    if ($null -eq $organization) {
        throw "The browser/session user cannot resolve the project's organization."
    }
    if ([string]$organization.role -eq "viewer") {
        throw "M3 operational verification requires an owner/admin/editor session to create the temporary dashboard panel."
    }

    $windowQuery = "start=$(Escape-QueryValue $smoke.start)&end=$(Escape-QueryValue $smoke.end)&limit=500"
    $catalog = Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/metrics/catalog/?$windowQuery" `
        -WebSession $session `
        -TimeoutSec 10
    $catalogMetric = @(
        $catalog.metrics | Where-Object { [string]$_.name -eq [string]$smoke.metric_name }
    ) | Select-Object -First 1
    if ($null -eq $catalogMetric -or -not [bool]$catalogMetric.supports_numeric_series) {
        throw "The fresh OTLP metric was not available as a scalar metric through the catalog API."
    }

    $seriesQuery = @(
        "metric_name=$(Escape-QueryValue $smoke.metric_name)",
        "start=$(Escape-QueryValue $smoke.start)",
        "end=$(Escape-QueryValue $smoke.end)",
        "service_name=$(Escape-QueryValue $smoke.service_name)",
        "environment=$(Escape-QueryValue $smoke.environment)",
        "limit=500"
    ) -join "&"
    $series = Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/metrics/series/?$seriesQuery" `
        -WebSession $session `
        -TimeoutSec 10
    $matchingPoints = @(
        $series.points | Where-Object { [double]$_.value -eq [double]$smoke.expected_value }
    )
    if ($matchingPoints.Count -lt 1) {
        throw "The numeric-series API did not return the freshly exported smoke value."
    }
    if ([string]$series.project_id -ne [string]$smoke.project_id) {
        throw "The numeric-series response project did not match the authenticated project."
    }
    if (
        [string]$series.filters.service_name -ne [string]$smoke.service_name -or
        [string]$series.filters.environment -ne [string]$smoke.environment
    ) {
        throw "The numeric-series API did not preserve the exact smoke service/environment filters."
    }

    Write-Host "== Temporary dashboard panel =="
    $panelsBeforeResponse = Invoke-WebRequest `
        -Uri "$apiBase/projects/$($smoke.project_id)/dashboard-panels/" `
        -WebSession $session `
        -TimeoutSec 10
    $panelsBefore = @($panelsBeforeResponse.Content | ConvertFrom-Json)
    if ($panelsBefore.Count -ge 6) {
        throw "M3 verification needs one temporary dashboard panel slot; this project already has six."
    }

    $panelBody = @{
        title = "M3 operational smoke $(([string]$smoke.run_id).Substring(0, 8))"
        metric_name = [string]$smoke.metric_name
        time_range = "1h"
        service_name = [string]$smoke.service_name
        environment = [string]$smoke.environment
    } | ConvertTo-Json -Compress
    $panel = Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/dashboard-panels/" `
        -Method Post `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -ContentType "application/json" `
        -Body $panelBody `
        -TimeoutSec 10
    $panelId = [string]$panel.id
    if ([string]::IsNullOrWhiteSpace($panelId)) {
        throw "Dashboard panel creation did not return an ID."
    }

    $panelsAfterResponse = Invoke-WebRequest `
        -Uri "$apiBase/projects/$($smoke.project_id)/dashboard-panels/" `
        -WebSession $session `
        -TimeoutSec 10
    $panelsAfter = @($panelsAfterResponse.Content | ConvertFrom-Json)
    if (-not ($panelsAfter | Where-Object { [string]$_.id -eq $panelId })) {
        throw "The temporary dashboard panel was not readable after creation."
    }

    $metricsUrl = "$webBase/orgs/$($organization.slug)/projects/$($project.slug)/metrics"
    $dashboardsUrl = "$webBase/orgs/$($organization.slug)/projects/$($project.slug)/dashboards"
    Write-Host ""
    Write-Host "Fresh smoke metric: $($smoke.metric_name)"
    Write-Host "Expected raw value: $($smoke.expected_value)"
    Write-Host "Metrics:    $metricsUrl"
    Write-Host "Dashboards: $dashboardsUrl"
    Write-Host ""
    Write-Host "Open both URLs before continuing. In Metrics, select the fresh smoke metric if needed."
    Write-Host "In Dashboards, confirm the temporary M3 operational panel shows the same raw value."
    $browserConfirmed = Read-Host "Did both browser views show the fresh metric/value correctly? [y/N]"
    if ($browserConfirmed.Trim().ToLowerInvariant() -notin @("y", "yes")) {
        throw "Browser verification was not confirmed."
    }

    Write-Host "== Cleanup temporary dashboard panel =="
    Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/dashboard-panels/$panelId/" `
        -Method Delete `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -TimeoutSec 10
    $panelId = $null

    if (-not $SkipReleaseGate) {
        Write-Host "== Full repository release gate =="
        & "$PSScriptRoot/verify.ps1"
    }

    Write-Host "M3 operational verification passed."
}
finally {
    if ($null -ne $panelId -and $null -ne $session) {
        try {
            Invoke-RestMethod `
                -Uri "$apiBase/projects/$($smoke.project_id)/dashboard-panels/$panelId/" `
                -Method Delete `
                -WebSession $session `
                -Headers (Get-CsrfHeader $session) `
                -TimeoutSec 10 `
                -ErrorAction Stop
        }
        catch {
            Write-Warning "Unable to remove temporary M3 dashboard panel $panelId automatically."
        }
    }
    $apiKey = $null
    $browserPassword = $null
    $smoke = $null
    Pop-Location
}
