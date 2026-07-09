param(
    [string]$Path = "observability/prometheus/alerts/interview-agent-alerts.yml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path)) {
    throw "Alert rules file not found: $Path"
}

$content = Get-Content -Raw -LiteralPath $Path

if ([string]::IsNullOrWhiteSpace($content)) {
    throw "Alert rules file is empty: $Path"
}

$requiredTokens = @(
    "groups:",
    "rules:",
    "alert:",
    "expr:",
    "labels:",
    "annotations:"
)

foreach ($token in $requiredTokens) {
    if ($content -notmatch [regex]::Escape($token)) {
        throw "Alert rules file is missing required token: $token"
    }
}

$alertCount = ([regex]::Matches($content, "(?m)^\s*-\s+alert:\s+\S+")).Count
if ($alertCount -lt 8) {
    throw "Expected at least 8 alert rules, found $alertCount"
}

$prometheusMetrics = @(
    "interview_agent_http_requests_total",
    "interview_agent_http_request_duration_seconds_bucket",
    "interview_agent_dependency_ready",
    "interview_agent_llm_calls_total",
    "interview_agent_llm_latency_seconds_bucket",
    "interview_agent_llm_estimated_cost_total",
    "interview_agent_rate_limit_exceeded_total",
    "interview_agent_quota_exceeded_total",
    "interview_agent_async_jobs_created_total",
    "interview_agent_async_jobs_completed_total",
    "interview_agent_async_jobs_in_progress"
)

foreach ($metric in $prometheusMetrics) {
    if ($content -notmatch [regex]::Escape($metric)) {
        throw "Expected alert rules to reference metric: $metric"
    }
}

Write-Host "Alert rules basic validation passed: $Path ($alertCount alerts)"
