param(
  [string]$FrontendBaseUrl = "",
  [string]$ApiBaseUrl = "",
  [string]$EnvFile = ".env.staging.example",
  [string]$ComposeFile = "docker-compose.yml",
  [string]$StagingComposeFile = "docker-compose.staging.yml",
  [switch]$SkipExternalChecks,
  [switch]$SkipBackup,
  [string]$OutputEvidencePath = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$results = [ordered]@{}

function Add-Result {
  param(
    [string]$Name,
    [string]$Status,
    [string]$Detail = ""
  )
  $results[$Name] = [pscustomobject]@{
    status = $Status
    detail = $Detail
  }
  $color = if ($Status -eq "pass") { "Green" } elseif ($Status -eq "skip") { "Yellow" } else { "Red" }
  Write-Host ("[{0}] {1} {2}" -f $Status.ToUpperInvariant(), $Name, $Detail) -ForegroundColor $color
}

function Test-RequiredPath {
  param([string]$Path)
  $fullPath = Join-Path $root $Path
  if (-not (Test-Path $fullPath)) {
    throw "Required path missing: $Path"
  }
}

function Get-ApiRoot {
  param([string]$Value)
  $trimmed = $Value.TrimEnd("/")
  if ($trimmed.EndsWith("/api")) {
    return $trimmed.Substring(0, $trimmed.Length - 4)
  }
  return $trimmed
}

function Invoke-DrillRequest {
  param(
    [string]$Name,
    [string]$Uri,
    [int[]]$AllowedStatusCodes = @(200)
  )
  $response = Invoke-WebRequest -Uri $Uri -Headers @{ "X-Request-ID" = "staging-drill" } -UseBasicParsing
  if ($AllowedStatusCodes -notcontains [int]$response.StatusCode) {
    throw "$Name expected status $($AllowedStatusCodes -join ',') but got $($response.StatusCode)"
  }
  return $response
}

function New-EvidenceSkeleton {
  param([hashtable]$CheckResults)
  $timestamp = (Get-Date).ToUniversalTime().ToString("o")
  $lines = @(
    "# Staging Deployment Drill Evidence",
    "",
    "- drill_id:",
    "- environment: staging",
    "- generated_at: $timestamp",
    "- commit_sha:",
    "- image_tag:",
    "- base_url:",
    "- api_base_url:",
    "",
    "## Automated Check Results"
  )
  foreach ($key in $CheckResults.Keys) {
    $value = $CheckResults[$key]
    $detail = if ($value.detail) { " - $($value.detail)" } else { "" }
    $lines += "- ${key}: $($value.status)$detail"
  }
  $lines += @(
    "",
    "## Manual Confirmation Required",
    "",
    "- real VPS/cloud host prepared:",
    "- runtime secrets configured outside git:",
    "- DB/Redis public exposure blocked:",
    "- metrics protected from public internet:",
    "- migration result reviewed:",
    "- backup file and SHA256 recorded:",
    "- restore drill target confirmed safe:",
    "- privacy export/delete checked with test user:",
    "- LLM Gateway route/fallback checked:",
    "- incident owner confirmed:",
    "- Go / No-Go decision:"
  )
  return ($lines -join [Environment]::NewLine)
}

Push-Location $root
try {
  $requiredPaths = @(
    "docs\staging-deployment.md",
    "docs\staging-deployment-drill.md",
    "docs\staging-deployment-drill-evidence-template.md",
    "docs\public-beta-readiness.md",
    "docs\public-beta-evidence-template.md",
    "docs\backup-and-restore.md",
    "docs\incident-runbook.md",
    "docs\metrics.md",
    "docs\llm-gateway.md",
    "scripts\staging-smoke.ps1",
    "scripts\backup-postgres.ps1",
    "scripts\restore-postgres.ps1",
    "scripts\verify-postgres-backup.ps1",
    "scripts\beta-readiness-check.ps1",
    $ComposeFile,
    $StagingComposeFile,
    $EnvFile
  )
  foreach ($path in $requiredPaths) {
    Test-RequiredPath $path
  }
  Add-Result "required_files" "pass" "required docs, scripts and compose files found"

  $envContent = Get-Content -Raw $EnvFile
  $requiredEnvMarkers = @(
    "APP_ENV=staging",
    "AUTH_DEV_CODE_ENABLED=false",
    "RATE_LIMIT_BACKEND=redis",
    "CACHE_BACKEND=redis",
    "REDIS_URL=",
    "DATABASE_URL=",
    "JWT_SECRET_KEY=",
    "NEXT_PUBLIC_API_BASE_URL=",
    "LLM_GATEWAY_ENABLED=true",
    "LLM_FALLBACK_ENABLED=true",
    "METRICS_ENABLED=true"
  )
  foreach ($marker in $requiredEnvMarkers) {
    if ($envContent -notmatch [regex]::Escape($marker)) {
      throw "Env file is missing marker: $marker"
    }
  }
  Add-Result "env_template" "pass" "staging markers found"

  docker compose --env-file $EnvFile -f $ComposeFile -f $StagingComposeFile config --quiet
  Add-Result "compose_config" "pass" "docker compose config succeeded"

  if ($SkipExternalChecks -or [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    Add-Result "external_api_checks" "skip" "no API URL or SkipExternalChecks"
  } else {
    $apiRoot = Get-ApiRoot $ApiBaseUrl
    $health = Invoke-DrillRequest -Name "health" -Uri "$apiRoot/health"
    if (-not $health.Headers["X-Request-ID"]) {
      throw "Health response did not include X-Request-ID"
    }
    Add-Result "health" "pass" "$apiRoot/health"

    $ready = Invoke-DrillRequest -Name "ready" -Uri "$apiRoot/ready"
    if ($ready.Content -notmatch '"status"\s*:\s*"ready"') {
      throw "Ready response did not report ready: $($ready.Content)"
    }
    Add-Result "ready" "pass" "$apiRoot/ready"

    $metrics = Invoke-DrillRequest -Name "metrics" -Uri "$apiRoot/metrics" -AllowedStatusCodes @(200, 403)
    Add-Result "metrics" "pass" "status $($metrics.StatusCode); should be trusted-path only"
  }

  if ($SkipExternalChecks -or [string]::IsNullOrWhiteSpace($FrontendBaseUrl) -or [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    Add-Result "staging_smoke" "skip" "no URLs or SkipExternalChecks"
  } else {
    & (Join-Path $root "scripts\staging-smoke.ps1") -BaseUrl $FrontendBaseUrl -ApiBaseUrl $ApiBaseUrl -RequestId "staging-drill"
    Add-Result "staging_smoke" "pass" "staging-smoke.ps1 completed"
  }

  if ($SkipBackup) {
    Add-Result "backup" "skip" "SkipBackup supplied"
  } else {
    Add-Result "backup" "skip" "run backup-postgres.ps1 manually against the real staging host"
  }

  $evidence = New-EvidenceSkeleton -CheckResults $results
  if (-not [string]::IsNullOrWhiteSpace($OutputEvidencePath)) {
    $outputFullPath = if ([System.IO.Path]::IsPathRooted($OutputEvidencePath)) {
      $OutputEvidencePath
    } else {
      Join-Path $root $OutputEvidencePath
    }
    $outputDir = Split-Path -Parent $outputFullPath
    if ($outputDir -and -not (Test-Path $outputDir)) {
      New-Item -ItemType Directory -Path $outputDir | Out-Null
    }
    Set-Content -Path $outputFullPath -Value $evidence -Encoding UTF8
    Add-Result "evidence_skeleton" "pass" $outputFullPath
  } else {
    Add-Result "evidence_skeleton" "pass" "generated in memory; pass OutputEvidencePath to write it"
  }

  Write-Host ""
  Write-Host "Staging deployment drill static checks completed." -ForegroundColor Green
  Write-Host "Restore is intentionally not executed by this script." -ForegroundColor Yellow
  Write-Host "Do not commit completed evidence if it contains internal URLs or operator details." -ForegroundColor Yellow
} finally {
  Pop-Location
}
