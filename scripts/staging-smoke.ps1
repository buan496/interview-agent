param(
  [string]$BaseUrl = "http://localhost:3000",
  [string]$ApiBaseUrl = "http://localhost:8000/api",
  [string]$RequestId = "staging-smoke"
)

$ErrorActionPreference = "Stop"

function Get-ApiRoot {
  param([string]$Value)
  $trimmed = $Value.TrimEnd("/")
  if ($trimmed.EndsWith("/api")) {
    return $trimmed.Substring(0, $trimmed.Length - 4)
  }
  return $trimmed
}

function Invoke-SmokeRequest {
  param(
    [string]$Name,
    [string]$Uri,
    [string]$Method = "GET",
    [object]$Body = $null,
    [int[]]$AllowedStatusCodes = @(200)
  )

  Write-Host "==> $Name" -ForegroundColor Cyan
  $headers = @{ "X-Request-ID" = $RequestId }
  $params = @{
    Uri = $Uri
    Method = $Method
    Headers = $headers
    UseBasicParsing = $true
  }
  if ($null -ne $Body) {
    $params.ContentType = "application/json"
    $params.Body = ($Body | ConvertTo-Json -Depth 8)
  }
  try {
    $response = Invoke-WebRequest @params
  } catch {
    if ($null -eq $_.Exception.Response) {
      throw
    }
    $errorResponse = $_.Exception.Response
    $reader = New-Object System.IO.StreamReader($errorResponse.GetResponseStream())
    $content = $reader.ReadToEnd()
    $headerMap = @{}
    foreach ($key in $errorResponse.Headers.AllKeys) {
      $headerMap[$key] = $errorResponse.Headers[$key]
    }
    $response = [pscustomobject]@{
      StatusCode = [int]$errorResponse.StatusCode
      Content = $content
      Headers = $headerMap
    }
  }
  if ($AllowedStatusCodes -notcontains [int]$response.StatusCode) {
    throw "$Name expected status $($AllowedStatusCodes -join ',') but got $($response.StatusCode): $($response.Content)"
  }
  return $response
}

$apiRoot = Get-ApiRoot $ApiBaseUrl
$base = $BaseUrl.TrimEnd("/")
$api = $ApiBaseUrl.TrimEnd("/")

$health = Invoke-SmokeRequest -Name "API health" -Uri "$apiRoot/health"
if (-not $health.Headers["X-Request-ID"]) {
  throw "API health response does not include X-Request-ID"
}

$ready = Invoke-SmokeRequest -Name "API readiness" -Uri "$apiRoot/ready"
$readyBody = $ready.Content | ConvertFrom-Json
if ($readyBody.status -ne "ready") {
  throw "API readiness status is not ready: $($ready.Content)"
}
if ($readyBody.PSObject.Properties.Name -contains "redis" -and $readyBody.redis -notin @("ok", "skipped")) {
  throw "API readiness returned unexpected Redis status: $($ready.Content)"
}

$metrics = Invoke-SmokeRequest -Name "API metrics" -Uri "$apiRoot/metrics"
if ($metrics.Content -notmatch "interview_agent_http_requests_total") {
  throw "API metrics response did not include expected HTTP request counter"
}

$loginPage = Invoke-SmokeRequest -Name "Frontend login page" -Uri "$base/login"
if ($loginPage.Content -notmatch "<html") {
  throw "Frontend login page did not return HTML"
}

$requestCode = Invoke-SmokeRequest `
  -Name "Staging auth code path" `
  -Uri "$api/auth/request-code" `
  -Method "POST" `
  -Body @{ phone = "18800000000" } `
  -AllowedStatusCodes @(200, 429, 503)
if ($requestCode.Content -match "development_code" -or $requestCode.Content -match "000000") {
  throw "Staging auth request-code exposed a development verification code"
}

Write-Host ""
Write-Host "Staging smoke passed." -ForegroundColor Green
Write-Host "API root: $apiRoot"
Write-Host "Frontend: $base"
Write-Host "Observed request id: $($health.Headers["X-Request-ID"])"
