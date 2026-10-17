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
$writeRoles = @("owner", "admin", "editor")
$session = $null
$browserPassword = $null
$apiKey = $null
$projectId = $null
$ruleId = $null
$channelId = $null
$signingSecret = $null
$foreignOrganizationId = $null
$receiverPid = $null
$receiverPort = $null
$receiverLog = $null
$receiverReady = $null
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

function Get-JsonArray([string]$uri, $webSession) {
    $response = Invoke-WebRequest -Uri $uri -WebSession $webSession -TimeoutSec 10
    return @($response.Content | ConvertFrom-Json)
}

function Assert-NotFound([string]$uri, $webSession) {
    try {
        $null = Invoke-WebRequest -Uri $uri -WebSession $webSession -TimeoutSec 10
    }
    catch {
        $response = $_.Exception.Response
        if ($null -ne $response -and [int]$response.StatusCode -eq 404) { return }
        throw
    }
    throw "Expected 404 for $uri."
}

function Get-WebhookRecords([string]$path) {
    $lines = @(
        docker compose exec -T api /bin/sh -c "cat '$path' 2>/dev/null || true"
    )
    return @(
        $lines |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { $_ | ConvertFrom-Json }
    )
}

function Wait-WebhookRecords([string]$path, [int]$expectedCount, [int]$timeoutSeconds = 15) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    do {
        $records = @(Get-WebhookRecords $path)
        if ($records.Count -ge $expectedCount) { return $records }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $expectedCount webhook record(s)."
}

function Assert-WebhookRecord(
    $record,
    [string]$secret,
    [string]$expectedEvent,
    [string]$expectedProjectId,
    [string]$expectedRuleId,
    [string]$expectedDeliveryId
) {
    if ([string]$record.path -ne "/sentrix") {
        throw "Webhook receiver observed an unexpected request path."
    }
    $bodyBytes = [Convert]::FromBase64String([string]$record.body_b64)
    $body = [Text.Encoding]::UTF8.GetString($bodyBytes)
    $timestamp = [string]$record.headers.'X-Sentrix-Timestamp'
    $actualSignature = [string]$record.headers.'X-Sentrix-Signature'
    $actualEvent = [string]$record.headers.'X-Sentrix-Event'
    $actualDeliveryId = [string]$record.headers.'X-Sentrix-Delivery'
    if ($actualDeliveryId -ne $expectedDeliveryId) {
        throw "Webhook delivery header did not match the persisted delivery row."
    }
    if ($actualEvent -ne "alert.$expectedEvent") {
        throw "Webhook event header did not match $expectedEvent."
    }

    $key = [Text.Encoding]::UTF8.GetBytes($secret)
    $message = [Text.Encoding]::UTF8.GetBytes("$timestamp.$body")
    $hmac = [Security.Cryptography.HMACSHA256]::new($key)
    try {
        $expectedSignature =
            "sha256=" + [Convert]::ToHexString($hmac.ComputeHash($message)).ToLowerInvariant()
    }
    finally {
        $hmac.Dispose()
    }
    if ($actualSignature -ne $expectedSignature) {
        throw "Webhook HMAC signature verification failed."
    }

    $payload = $body | ConvertFrom-Json
    if ([string]$payload.event -ne "sentrix.alert.$expectedEvent") {
        throw "Webhook payload event did not match $expectedEvent."
    }
    if ([string]$payload.project_id -ne $expectedProjectId) {
        throw "Webhook payload project did not match the temporary verification project."
    }
    if ([string]$payload.alert_rule.id -ne $expectedRuleId) {
        throw "Webhook payload rule did not match the temporary verification rule."
    }
    if ($payload.state.PSObject.Properties.Name -contains "value") {
        throw "Webhook payload unexpectedly copied an observed metric value into PostgreSQL payload state."
    }
}

function Remove-ForeignOrganization([string]$organizationId) {
    if ([string]::IsNullOrWhiteSpace($organizationId)) { return }
    $cleanup = @'
import os
from uuid import UUID

from apps.organizations.models import Organization

Organization.objects.filter(pk=UUID(os.environ["SENTRIX_M5_FOREIGN_ORG_ID"])).delete()
'@
    $cleanup | docker compose exec -T `
        -e SENTRIX_M5_FOREIGN_ORG_ID=$organizationId `
        api /opt/venv/bin/python manage.py shell | Out-Null
    Assert-ExitCode "Unable to remove the temporary M5 foreign organization."
}

Push-Location $repoRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not on PATH."
    }

    Write-Host "== M5 Compose stack =="
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

    $policyOutput = @(
        docker compose exec -T api /opt/venv/bin/python manage.py shell -c `
            "import json; from django.conf import settings; print(json.dumps({'hosts': settings.NOTIFICATION_WEBHOOK_ALLOWED_HOSTS, 'allow_http': settings.NOTIFICATION_WEBHOOK_ALLOW_HTTP}))"
    )
    Assert-ExitCode "Unable to inspect the local webhook egress policy."
    $policy = $policyOutput[-1] | ConvertFrom-Json
    if (
        -not [bool]$policy.allow_http -or
        "127.0.0.1" -notin @($policy.hosts)
    ) {
        throw (
            "M5 operational verification requires local HTTP webhook egress to 127.0.0.1. " +
            "Use the repository development defaults or explicitly allow that loopback host."
        )
    }

    Write-Host "== Browser/session authentication =="
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

    $organizations = @(Get-JsonArray "$apiBase/organizations/" $session)
    $writableOrganizations = @(
        $organizations | Where-Object { [string]$_.role -in $writeRoles }
    )
    if ($writableOrganizations.Count -eq 0) {
        throw "M5 verification requires owner/admin/editor membership in at least one organization."
    }

    $requestedOrganizationSlug = $env:SENTRIX_M5_ORGANIZATION_SLUG
    if (-not [string]::IsNullOrWhiteSpace($requestedOrganizationSlug)) {
        $organization = @(
            $writableOrganizations |
                Where-Object { [string]$_.slug -eq $requestedOrganizationSlug }
        ) | Select-Object -First 1
        if ($null -eq $organization) {
            throw "SENTRIX_M5_ORGANIZATION_SLUG is not a writable organization for this session."
        }
    }
    elseif ($writableOrganizations.Count -eq 1) {
        $organization = $writableOrganizations[0]
    }
    else {
        Write-Host "Writable organizations: $($writableOrganizations.slug -join ', ')"
        $requestedOrganizationSlug = Read-Host "Organization slug for the temporary M5 project"
        $organization = @(
            $writableOrganizations |
                Where-Object { [string]$_.slug -eq $requestedOrganizationSlug }
        ) | Select-Object -First 1
        if ($null -eq $organization) {
            throw "The selected organization is not writable by this session."
        }
    }

    $runId = [Guid]::NewGuid().ToString("N")
    $suffix = $runId.Substring(0, 8)
    $receiverPort = Get-Random -Minimum 18000 -Maximum 19000
    Write-Host "== Temporary isolated M5 project =="
    $projectBody = @{
        organization_id = [string]$organization.id
        name = "M5 operational smoke $suffix"
        slug = "m5-operational-$suffix"
    } | ConvertTo-Json -Compress
    $project = Invoke-RestMethod `
        -Uri "$apiBase/projects/" `
        -Method Post `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -ContentType "application/json" `
        -Body $projectBody `
        -TimeoutSec 10
    $projectId = [string]$project.id
    if ([string]::IsNullOrWhiteSpace($projectId)) {
        throw "Temporary M5 project creation did not return an ID."
    }

    $apiKeyBody = @{ name = "M5 operational telemetry $suffix" } | ConvertTo-Json -Compress
    $createdApiKey = Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/api-keys/" `
        -Method Post `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -ContentType "application/json" `
        -Body $apiKeyBody `
        -TimeoutSec 10
    $apiKey = [string]$createdApiKey.secret
    if ([string]::IsNullOrWhiteSpace($apiKey) -or -not $apiKey.StartsWith("sentrix_pk_")) {
        throw "Temporary project API-key creation did not return a valid one-time secret."
    }

    Write-Host "== Real OTLP firing metric =="
    $smokeOutput = @(
        $apiKey | docker compose exec -T -e PYTHONPATH=/app api `
            /opt/venv/bin/python scripts/otlp_alert_smoke.py `
            --phase firing --value 42
    )
    Assert-ExitCode "M5 firing OTLP metric smoke failed."
    if ($smokeOutput.Count -lt 1) { throw "M5 metric smoke returned no verification metadata." }
    $smoke = $smokeOutput[-1] | ConvertFrom-Json
    if (
        [string]$smoke.project_id -ne $projectId -or
        [string]$smoke.organization_id -ne [string]$organization.id
    ) {
        throw "OTLP smoke tenant identity did not match the temporary project credential."
    }

    Write-Host "== Temporary alert rule and notification channel =="
    $ruleBody = @{
        name = "M5 operational smoke $suffix"
        metric_name = [string]$smoke.metric_name
        time_range = "1h"
        service_name = [string]$smoke.service_name
        environment = [string]$smoke.environment
        comparator = "gt"
        threshold = 10
        enabled = $true
    } | ConvertTo-Json -Compress
    $rule = Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/alert-rules/" `
        -Method Post `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -ContentType "application/json" `
        -Body $ruleBody `
        -TimeoutSec 10
    $ruleId = [string]$rule.id
    if ([string]$rule.state.status -ne "pending") {
        throw "Fresh M5 verification rule did not start pending."
    }

    $channelBody = @{
        name = "M5 operational webhook $suffix"
        endpoint_url = "http://127.0.0.1:$receiverPort/sentrix"
        enabled = $true
    } | ConvertTo-Json -Compress
    $channel = Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/notification-channels/" `
        -Method Post `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -ContentType "application/json" `
        -Body $channelBody `
        -TimeoutSec 10
    $channelId = [string]$channel.id
    $signingSecret = [string]$channel.signing_secret
    if ([string]::IsNullOrWhiteSpace($channelId) -or [string]::IsNullOrWhiteSpace($signingSecret)) {
        throw "Temporary webhook channel did not return its ID and one-time signing secret."
    }

    $channelList = @(
        Get-JsonArray "$apiBase/projects/$projectId/notification-channels/" $session
    )
    $safeChannel = @($channelList | Where-Object { [string]$_.id -eq $channelId }) |
        Select-Object -First 1
    if ($null -eq $safeChannel) {
        throw "Temporary webhook channel was not readable after creation."
    }
    if (
        $safeChannel.PSObject.Properties.Name -contains "signing_secret" -or
        $safeChannel.PSObject.Properties.Name -contains "endpoint_url"
    ) {
        throw "Notification channel read unexpectedly exposed secret endpoint configuration."
    }

    Write-Host "== Foreign-project nondiscovery =="
    $foreignSetup = @'
import json
import os
from uuid import uuid4

from django.contrib.auth.models import User

from apps.organizations.models import Organization
from apps.projects.models import Project

suffix = uuid4().hex[:10]
user = User.objects.get(username=os.environ["SENTRIX_M5_BROWSER_USERNAME"])
organization = Organization.objects.create(
    name=f"M5 foreign smoke {suffix}",
    slug=f"m5-foreign-{suffix}",
)
project = Project.objects.create(
    organization=organization,
    name="M5 foreign smoke",
    slug="app",
    created_by=user,
)
print(json.dumps({"organization_id": str(organization.id), "project_id": str(project.id)}))
'@
    $foreignOutput = @(
        $foreignSetup | docker compose exec -T `
            -e SENTRIX_M5_BROWSER_USERNAME=$browserUsername `
            api /opt/venv/bin/python manage.py shell
    )
    Assert-ExitCode "Unable to create the disposable foreign-project isolation fixture."
    $foreign = $foreignOutput[-1] | ConvertFrom-Json
    $foreignOrganizationId = [string]$foreign.organization_id
    $foreignProjectId = [string]$foreign.project_id
    Assert-NotFound "$apiBase/projects/$foreignProjectId/alert-rules/" $session
    Assert-NotFound "$apiBase/projects/$foreignProjectId/alert-rules/$ruleId/" $session
    Assert-NotFound "$apiBase/projects/$foreignProjectId/notification-channels/" $session
    Assert-NotFound "$apiBase/projects/$foreignProjectId/notification-channels/$channelId/" $session

    Write-Host "== Disposable local webhook receiver =="
    $receiverLog = "/tmp/sentrix-m5-webhook-$runId.jsonl"
    $receiverReady = "/tmp/sentrix-m5-webhook-$runId.ready.json"
    docker compose exec -T api rm -f $receiverLog $receiverReady
    Assert-ExitCode "Unable to clear stale M5 receiver files."
    docker compose exec -d api `
        /opt/venv/bin/python scripts/m5_webhook_receiver.py `
        --host 127.0.0.1 `
        --port $receiverPort `
        --output $receiverLog `
        --ready-file $receiverReady `
        --max-requests 2
    Assert-ExitCode "Unable to start the disposable M5 webhook receiver."

    $receiverDeadline = (Get-Date).AddSeconds(10)
    do {
        $readyText = @(
            docker compose exec -T api /bin/sh -c "cat '$receiverReady' 2>/dev/null || true"
        ) -join ""
        if (-not [string]::IsNullOrWhiteSpace($readyText)) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $receiverDeadline)
    if ([string]::IsNullOrWhiteSpace($readyText)) {
        throw "Disposable M5 webhook receiver did not become ready."
    }
    $receiverMetadata = $readyText | ConvertFrom-Json
    $receiverPid = [int]$receiverMetadata.pid

    Write-Host "== Firing evaluation and signed delivery =="
    docker compose exec -T api /opt/venv/bin/python manage.py evaluate_alerts --project-id $projectId
    Assert-ExitCode "M5 firing evaluation failed."
    $rule = Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/alert-rules/$ruleId/" `
        -WebSession $session `
        -TimeoutSec 10
    if ([string]$rule.state.status -ne "firing") {
        throw "The real OTLP firing metric did not move the temporary rule to firing."
    }
    $deliveries = @(
        Get-JsonArray "$apiBase/projects/$projectId/notification-deliveries/?limit=20" $session
    )
    if (
        $deliveries.Count -ne 1 -or
        [string]$deliveries[0].event_type -ne "firing" -or
        [string]$deliveries[0].status -ne "pending"
    ) {
        throw "Firing transition did not create exactly one pending firing delivery."
    }
    $firingDeliveryId = [string]$deliveries[0].id

    docker compose exec -T api `
        /opt/venv/bin/python manage.py dispatch_notifications --project-id $projectId --limit 20
    Assert-ExitCode "M5 firing notification dispatch failed."
    $records = @(Wait-WebhookRecords $receiverLog 1)
    Assert-WebhookRecord `
        $records[0] $signingSecret "firing" $projectId $ruleId $firingDeliveryId

    Write-Host "== Same-state deduplication =="
    docker compose exec -T api /opt/venv/bin/python manage.py evaluate_alerts --project-id $projectId
    Assert-ExitCode "M5 repeated firing evaluation failed."
    $deliveries = @(
        Get-JsonArray "$apiBase/projects/$projectId/notification-deliveries/?limit=20" $session
    )
    if ($deliveries.Count -ne 1) {
        throw "Repeated firing evaluation created a duplicate notification delivery."
    }
    docker compose exec -T api `
        /opt/venv/bin/python manage.py dispatch_notifications --project-id $projectId --limit 20
    Assert-ExitCode "M5 no-op notification dispatch failed."

    Write-Host "== Real OTLP recovery metric =="
    $recoveryOutput = @(
        $apiKey | docker compose exec -T -e PYTHONPATH=/app api `
            /opt/venv/bin/python scripts/otlp_alert_smoke.py `
            --phase recovery `
            --value 5 `
            --run-id $($smoke.run_id) `
            --metric-name $($smoke.metric_name)
    )
    Assert-ExitCode "M5 recovery OTLP metric smoke failed."
    $recovery = $recoveryOutput[-1] | ConvertFrom-Json
    if (
        [string]$recovery.project_id -ne $projectId -or
        [string]$recovery.metric_name -ne [string]$smoke.metric_name -or
        [double]$recovery.expected_value -ne 5
    ) {
        throw "M5 recovery OTLP metadata did not match the temporary verification rule."
    }

    docker compose exec -T api /opt/venv/bin/python manage.py evaluate_alerts --project-id $projectId
    Assert-ExitCode "M5 recovery evaluation failed."
    $rule = Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/alert-rules/$ruleId/" `
        -WebSession $session `
        -TimeoutSec 10
    if ([string]$rule.state.status -ne "ok") {
        throw "The real OTLP recovery metric did not move the temporary rule to ok."
    }
    $deliveries = @(
        Get-JsonArray "$apiBase/projects/$projectId/notification-deliveries/?limit=20" $session
    )
    $firingDeliveries = @($deliveries | Where-Object { [string]$_.event_type -eq "firing" })
    $recoveryDeliveries = @($deliveries | Where-Object { [string]$_.event_type -eq "recovered" })
    if (
        $deliveries.Count -ne 2 -or
        $firingDeliveries.Count -ne 1 -or
        $recoveryDeliveries.Count -ne 1 -or
        [string]$recoveryDeliveries[0].status -ne "pending"
    ) {
        throw "Recovery transition did not create exactly one pending recovery delivery."
    }
    $recoveryDeliveryId = [string]$recoveryDeliveries[0].id

    docker compose exec -T api `
        /opt/venv/bin/python manage.py dispatch_notifications --project-id $projectId --limit 20
    Assert-ExitCode "M5 recovery notification dispatch failed."
    $records = @(Wait-WebhookRecords $receiverLog 2)
    if ($records.Count -ne 2) {
        throw "Disposable receiver did not observe exactly firing and recovery webhooks."
    }
    Assert-WebhookRecord `
        $records[0] $signingSecret "firing" $projectId $ruleId $firingDeliveryId
    Assert-WebhookRecord `
        $records[1] $signingSecret "recovered" $projectId $ruleId $recoveryDeliveryId

    $deliveries = @(
        Get-JsonArray "$apiBase/projects/$projectId/notification-deliveries/?limit=20" $session
    )
    $notDelivered = @(
        $deliveries | Where-Object {
            [string]$_.status -ne "delivered" -or
            [int]$_.attempt_count -ne 1 -or
            [int]$_.response_status -ne 204
        }
    )
    if ($deliveries.Count -ne 2 -or $notDelivered.Count -ne 0) {
        throw "M5 delivery API did not show two successful one-attempt deliveries."
    }

    $alertsUrl = "$webBase/orgs/$($organization.slug)/projects/$($project.slug)/alerts"
    Write-Host ""
    Write-Host "Fresh M5 metric: $($smoke.metric_name)"
    Write-Host "Temporary rule: $($rule.name)"
    Write-Host "Final persisted state: $($rule.state.status)"
    Write-Host "Alerts: $alertsUrl"
    Write-Host ""
    Write-Host "Open the Alerts URL and confirm the temporary rule is visible with current state 'ok'."
    $browserConfirmed = Read-Host "Did the real Alerts workspace show the temporary rule/state correctly? [y/N]"
    if ($browserConfirmed.Trim().ToLowerInvariant() -notin @("y", "yes")) {
        throw "M5 browser verification was not confirmed."
    }

    Write-Host "== Cleanup temporary M5 control-plane records =="
    Invoke-RestMethod `
        -Uri "$apiBase/projects/$projectId/" `
        -Method Delete `
        -WebSession $session `
        -Headers (Get-CsrfHeader $session) `
        -TimeoutSec 10
    $projectId = $null
    $ruleId = $null
    $channelId = $null
    Remove-ForeignOrganization $foreignOrganizationId
    $foreignOrganizationId = $null

    if (-not $SkipReleaseGate) {
        Write-Host "== Full repository release gate =="
        & "$PSScriptRoot/verify.ps1"
    }

    Write-Host "M5 operational verification passed."
}
finally {
    if ($null -ne $projectId -and $null -ne $session) {
        try {
            Invoke-RestMethod `
                -Uri "$apiBase/projects/$projectId/" `
                -Method Delete `
                -WebSession $session `
                -Headers (Get-CsrfHeader $session) `
                -TimeoutSec 10 `
                -ErrorAction Stop
        }
        catch {
            Write-Warning "Unable to remove temporary M5 project $projectId automatically."
        }
    }
    if ($null -ne $foreignOrganizationId) {
        try {
            Remove-ForeignOrganization $foreignOrganizationId
        }
        catch {
            Write-Warning "Unable to remove temporary M5 foreign organization automatically."
        }
    }
    if ($null -ne $receiverPid) {
        docker compose exec -T api kill $receiverPid 2>$null | Out-Null
    }
    if ($null -ne $receiverLog) {
        docker compose exec -T api rm -f $receiverLog 2>$null | Out-Null
    }
    if ($null -ne $receiverReady) {
        docker compose exec -T api rm -f $receiverReady 2>$null | Out-Null
    }
    $apiKey = $null
    $signingSecret = $null
    $browserPassword = $null
    $smoke = $null
    $session = $null
    Pop-Location
}
