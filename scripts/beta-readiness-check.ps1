param(
  [string]$ApiBaseUrl = "",
  [string]$FrontendBaseUrl = ""
)

$ErrorActionPreference = "Stop"

function Assert-PathExists {
  param(
    [string]$Path,
    [string]$Description
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Missing $Description`: $Path"
  }
  Write-Host "OK: $Description" -ForegroundColor Green
}

function Assert-FileContains {
  param(
    [string]$Path,
    [string]$Pattern,
    [string]$Description
  )

  if (-not (Select-String -LiteralPath $Path -Pattern $Pattern -Quiet)) {
    throw "Missing $Description in $Path"
  }
  Write-Host "OK: $Description" -ForegroundColor Green
}

function Invoke-OptionalHttpCheck {
  param(
    [string]$Name,
    [string]$Uri,
    [int]$ExpectedStatus = 200
  )

  if ([string]::IsNullOrWhiteSpace($Uri)) {
    return
  }

  Write-Host "Checking $Name`: $Uri"
  try {
    $response = Invoke-WebRequest -Uri $Uri -Method GET -TimeoutSec 15 -Headers @{ "X-Request-ID" = "beta-readiness-check" }
  } catch {
    throw "$Name check failed for $Uri. $($_.Exception.Message)"
  }

  if ([int]$response.StatusCode -ne $ExpectedStatus) {
    throw "$Name returned status $($response.StatusCode), expected $ExpectedStatus"
  }
  Write-Host "OK: $Name" -ForegroundColor Green
}

Assert-PathExists "docs/public-beta-readiness.md" "public beta readiness document"
Assert-PathExists "docs/public-beta-evidence-template.md" "public beta evidence template"
Assert-PathExists "docs/staging-deployment.md" "staging deployment document"
Assert-PathExists "docs/staging-deployment-drill.md" "staging deployment drill document"
Assert-PathExists "docs/staging-deployment-drill-evidence-template.md" "staging deployment drill evidence template"
Assert-PathExists "docs/release-management.md" "release management document"
Assert-PathExists "docs/release-evidence-template.md" "release evidence template"
Assert-PathExists "docs/backup-and-restore.md" "backup and restore document"
Assert-PathExists "docs/backup-evidence-template.md" "backup evidence template"
Assert-PathExists "docs/alerting.md" "alerting document"
Assert-PathExists "docs/incident-runbook.md" "incident runbook"
Assert-PathExists "docs/incident-evidence-template.md" "incident evidence template"
Assert-PathExists "docs/privacy-and-data-lifecycle.md" "privacy lifecycle document"
Assert-PathExists "docs/llm-gateway.md" "LLM gateway document"
Assert-PathExists "docs/evaluation-harness.md" "evaluation harness document"
Assert-PathExists "docs/async-jobs.md" "async jobs document"
Assert-PathExists "docs/metrics.md" "metrics document"
Assert-PathExists "docs/observability.md" "observability document"
Assert-PathExists "observability/prometheus/alerts/interview-agent-alerts.yml" "Prometheus alert rules"

Assert-PathExists ".env.example" "local env example"
Assert-PathExists ".env.staging.example" "staging env example"
Assert-PathExists "docker-compose.staging.yml" "staging compose file"
Assert-PathExists "scripts/staging-smoke.ps1" "staging smoke script"
Assert-PathExists "scripts/check-alert-rules.ps1" "alert rules check script"
Assert-PathExists "scripts/backup-postgres.ps1" "PostgreSQL backup script"
Assert-PathExists "scripts/restore-postgres.ps1" "PostgreSQL restore script"
Assert-PathExists "scripts/verify-postgres-backup.ps1" "PostgreSQL backup verification script"
Assert-PathExists "scripts/staging-deployment-drill.ps1" "staging deployment drill script"
Assert-PathExists "scripts/run-eval.ps1" "evaluation runner script"
Assert-PathExists "evals/datasets/interview_scoring_smoke.jsonl" "sanitized interview scoring eval dataset"

Assert-FileContains ".env.staging.example" "^APP_ENV=staging" "staging APP_ENV"
Assert-FileContains ".env.staging.example" "^AUTH_DEV_CODE_ENABLED=false" "staging dev auth disabled"
Assert-FileContains ".env.staging.example" "^JWT_SECRET_KEY=__CHANGE_ME" "staging JWT secret placeholder"
Assert-FileContains ".env.staging.example" "^DATABASE_URL=" "staging database URL"
Assert-FileContains ".env.staging.example" "^REDIS_URL=" "staging Redis URL"
Assert-FileContains ".env.staging.example" "^RATE_LIMIT_ENABLED=true" "staging rate limit enabled"
Assert-FileContains ".env.staging.example" "^RATE_LIMIT_BACKEND=redis" "staging Redis rate-limit backend"
Assert-FileContains ".env.staging.example" "^CACHE_BACKEND=redis" "staging Redis cache backend"
Assert-FileContains ".env.staging.example" "^LLM_USAGE_METERING_ENABLED=true" "staging LLM usage metering enabled"
Assert-FileContains ".env.staging.example" "^LLM_FALLBACK_ENABLED=true" "staging LLM fallback enabled"
Assert-FileContains ".env.staging.example" "^NEXT_PUBLIC_API_BASE_URL=" "staging frontend API base URL"
Assert-FileContains ".env.staging.example" "^METRICS_ENABLED=true" "staging metrics enabled"

Assert-FileContains "docs/public-beta-readiness.md" "GO / NO-GO" "go/no-go section"
Assert-FileContains "docs/public-beta-readiness.md" "Beta Forbidden Items" "beta forbidden items section"
Assert-FileContains "docs/public-beta-readiness.md" "Beta Operation SOP" "beta operation SOP section"
Assert-FileContains "docs/public-beta-readiness.md" "AUTH_DEV_CODE_ENABLED=false" "dev auth disabled checklist item"
Assert-FileContains "docs/public-beta-readiness.md" "DELETE_MY_DATA" "privacy deletion confirmation reference"
Assert-FileContains "docs/public-beta-readiness.md" "Real staging deployment drill" "real staging drill gate"
Assert-FileContains "docs/public-beta-readiness.md" "Mock Evaluation Harness" "mock eval gate"
Assert-FileContains "docs/public-beta-evidence-template.md" "staging deployment drill evidence" "staging drill evidence field"
Assert-FileContains "docs/public-beta-evidence-template.md" "mock evaluation harness result" "mock eval evidence field"

if (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
  $apiRoot = $ApiBaseUrl.TrimEnd("/")
  if ($apiRoot.EndsWith("/api")) {
    $apiRoot = $apiRoot.Substring(0, $apiRoot.Length - 4)
  }
  Invoke-OptionalHttpCheck -Name "API health" -Uri "$apiRoot/health"
  Invoke-OptionalHttpCheck -Name "API readiness" -Uri "$apiRoot/ready"
}

if (-not [string]::IsNullOrWhiteSpace($FrontendBaseUrl)) {
  $frontendRoot = $FrontendBaseUrl.TrimEnd("/")
  Invoke-OptionalHttpCheck -Name "Frontend" -Uri $frontendRoot
}

Write-Host "Public beta readiness local checks passed." -ForegroundColor Green
