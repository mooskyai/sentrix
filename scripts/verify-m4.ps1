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

function Get-JsonPropertyValue([object]$inputObject, [string]$name) {
    if ($null -eq $inputObject) { return $null }
    $property = $inputObject.PSObject.Properties[$name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

Push-Location $repoRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not on PATH."
    }

    Write-Host "== M4 Compose stack =="
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

    Write-Host "== Correlated OTLP/HTTP log and trace export =="
    $smokeOutput = @(
        $apiKey | docker compose exec -T -e PYTHONPATH=/app api `
            /opt/venv/bin/python scripts/otlp_log_trace_smoke.py
    )
    Assert-ExitCode "Correlated OTLP log/trace operational smoke failed."
    if ($smokeOutput.Count -lt 1) { throw "M4 smoke did not return verification metadata." }
    try {
        $smoke = $smokeOutput[-1] | ConvertFrom-Json
    }
    catch {
        throw "M4 smoke returned invalid verification metadata."
    }

    Write-Host "Verified durable correlated telemetry for project $($smoke.project_id)."
    Write-Host "Trace ID: $($smoke.trace_id)"

    Write-Host "== Session-authenticated M4 query path =="
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
    $project = @(
        $projects | Where-Object { [string]$_.id -eq [string]$smoke.project_id }
    ) | Select-Object -First 1
    if ($null -eq $project) {
        throw "The browser/session user cannot access the project bound to the supplied telemetry key."
    }
    $organization = @(
        $organizations | Where-Object { [string]$_.id -eq [string]$project.organization_id }
    ) | Select-Object -First 1
    if ($null -eq $organization) {
        throw "The browser/session user cannot resolve the project's organization."
    }

    $logQuery = @(
        "start=$(Escape-QueryValue $smoke.start)",
        "end=$(Escape-QueryValue $smoke.end)",
        "limit=20",
        "service_name=$(Escape-QueryValue $smoke.service_name)",
        "environment=$(Escape-QueryValue $smoke.environment)",
        "min_severity_number=17",
        "body_contains=$(Escape-QueryValue $smoke.run_id)",
        "trace_id=$(Escape-QueryValue $smoke.trace_id)"
    ) -join "&"
    $logs = Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/logs/search/?$logQuery" `
        -WebSession $session `
        -TimeoutSec 10
    if ([string]$logs.project_id -ne [string]$smoke.project_id) {
        throw "The log-search response project did not match the authenticated project."
    }
    if ([bool]$logs.truncated) {
        throw "The bounded M4 operational log query unexpectedly truncated."
    }
    if (
        [string]$logs.filters.service_name -ne [string]$smoke.service_name -or
        [string]$logs.filters.environment -ne [string]$smoke.environment -or
        [int]$logs.filters.min_severity_number -ne 17 -or
        [string]$logs.filters.body_contains -ne [string]$smoke.run_id -or
        [string]$logs.filters.trace_id -ne [string]$smoke.trace_id
    ) {
        throw "The log-search API did not preserve the exact M4 smoke filters."
    }

    $matchingLogs = @(
        $logs.logs | Where-Object {
            [string]$_.trace_id -eq [string]$smoke.trace_id -and
            [string]$_.span_id -eq [string]$smoke.child_span_id -and
            [string]$_.body -eq [string]$smoke.log_body
        }
    )
    if ($matchingLogs.Count -ne 1) {
        throw "The session-authenticated log API did not return exactly one fresh correlated smoke row."
    }
    $matchingLog = $matchingLogs[0]
    if (
        [string]$matchingLog.service_name -ne [string]$smoke.service_name -or
        [string]$matchingLog.environment -ne [string]$smoke.environment -or
        [int]$matchingLog.severity_number -ne 17
    ) {
        throw "The M4 log API did not preserve service/environment/severity."
    }
    if (
        [string](Get-JsonPropertyValue $matchingLog.attributes "sentrix.smoke.run") -ne
        [string]$smoke.run_id
    ) {
        throw "The M4 log API did not preserve the smoke record attribute."
    }

    $traceQuery = @(
        "start=$(Escape-QueryValue $smoke.start)",
        "end=$(Escape-QueryValue $smoke.end)",
        "limit=20"
    ) -join "&"
    $trace = Invoke-RestMethod `
        -Uri "$apiBase/projects/$($smoke.project_id)/traces/$($smoke.trace_id)/?$traceQuery" `
        -WebSession $session `
        -TimeoutSec 10
    if ([string]$trace.project_id -ne [string]$smoke.project_id) {
        throw "The trace response project did not match the authenticated project."
    }
    if ([string]$trace.trace_id -ne [string]$smoke.trace_id) {
        throw "The trace API did not return the requested trace ID."
    }
    if ([bool]$trace.truncated) {
        throw "The bounded M4 operational trace query unexpectedly truncated."
    }

    $rootSpan = @(
        $trace.spans | Where-Object { [string]$_.span_id -eq [string]$smoke.root_span_id }
    ) | Select-Object -First 1
    $childSpan = @(
        $trace.spans | Where-Object { [string]$_.span_id -eq [string]$smoke.child_span_id }
    ) | Select-Object -First 1
    if ($null -eq $rootSpan -or $null -eq $childSpan) {
        throw "The trace API did not return both fresh smoke spans."
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$rootSpan.parent_span_id)) {
        throw "The trace API did not preserve the smoke root span as root."
    }
    if ([string]$childSpan.parent_span_id -ne [string]$smoke.root_span_id) {
        throw "The trace API did not preserve child-to-root parentage."
    }
    if (
        [string]$rootSpan.span_name -ne [string]$smoke.root_span_name -or
        [string]$childSpan.span_name -ne [string]$smoke.child_span_name -or
        [int]$rootSpan.status_code -ne 1 -or
        [int]$childSpan.status_code -ne 2
    ) {
        throw "The trace API did not preserve the expected span names/status values."
    }
    if (
        [string]$rootSpan.service_name -ne [string]$smoke.service_name -or
        [string]$childSpan.service_name -ne [string]$smoke.service_name -or
        [string]$rootSpan.environment -ne [string]$smoke.environment -or
        [string]$childSpan.environment -ne [string]$smoke.environment
    ) {
        throw "The trace API did not preserve service/environment."
    }
    if (
        [string](Get-JsonPropertyValue $childSpan.attributes "sentrix.smoke.run") -ne
        [string]$smoke.run_id
    ) {
        throw "The trace API did not preserve the child smoke attribute."
    }
    if ([string]$childSpan.events_json -notmatch [Regex]::Escape([string]$smoke.event_name)) {
        throw "The trace API did not preserve the child smoke event JSON."
    }

    $organizationSlug = [Uri]::EscapeDataString([string]$organization.slug)
    $projectSlug = [Uri]::EscapeDataString([string]$project.slug)
    $logsUrl = "$webBase/orgs/$organizationSlug/projects/$projectSlug/logs"
    $traceUrl = "$webBase/orgs/$organizationSlug/projects/$projectSlug/traces?" + (
        @(
            "trace_id=$(Escape-QueryValue $smoke.trace_id)",
            "start=$(Escape-QueryValue $smoke.start)",
            "end=$(Escape-QueryValue $smoke.end)"
        ) -join "&"
    )

    Write-Host ""
    Write-Host "Fresh correlated log body: $($smoke.log_body)"
    Write-Host "Service:   $($smoke.service_name)"
    Write-Host "Environment: $($smoke.environment)"
    Write-Host "Trace ID:  $($smoke.trace_id)"
    Write-Host "Root span: $($smoke.root_span_name) / $($smoke.root_span_id)"
    Write-Host "Child span: $($smoke.child_span_name) / $($smoke.child_span_id)"
    Write-Host "Logs:      $logsUrl"
    Write-Host "Trace:     $traceUrl"
    Write-Host ""
    Write-Host "Open Logs, filter by the fresh Trace ID if needed, then use Open trace."
    Write-Host "Confirm the trace view shows the root and child with the real parent relationship."
    $browserConfirmed = Read-Host "Did the Logs -> Open trace browser flow show this telemetry correctly? [y/N]"
    if ($browserConfirmed.Trim().ToLowerInvariant() -notin @("y", "yes")) {
        throw "Browser verification was not confirmed."
    }

    if (-not $SkipReleaseGate) {
        Write-Host "== Full repository release gate =="
        & "$PSScriptRoot/verify.ps1"
    }

    Write-Host "M4 operational verification passed."
}
finally {
    $apiKey = $null
    $browserPassword = $null
    $smoke = $null
    $session = $null
    Pop-Location
}
