param(
  [ValidateSet("local", "staging")]
  [string]$Environment = "local",
  [string[]]$ComposeFile = @(),
  [string]$EnvFile = "",
  [string]$OutputDir = "backups",
  [string]$ServiceName = "postgres",
  [string]$DatabaseName = "",
  [string]$DatabaseUser = ""
)

$ErrorActionPreference = "Stop"

function Get-DefaultComposeFiles {
  param([string]$TargetEnvironment)
  if ($TargetEnvironment -eq "staging") {
    return @("docker-compose.staging.yml")
  }
  return @("docker-compose.yml")
}

function Get-DefaultDatabaseName {
  param([string]$TargetEnvironment)
  if ($TargetEnvironment -eq "staging") {
    return "interview_agent_staging"
  }
  return "interview_agent"
}

function New-ComposeArgs {
  param(
    [string[]]$Files,
    [string]$OptionalEnvFile
  )
  $args = @("compose")
  if ($OptionalEnvFile) {
    $args += @("--env-file", $OptionalEnvFile)
  }
  foreach ($file in $Files) {
    $args += @("-f", $file)
  }
  return $args
}

if ($ComposeFile.Count -eq 0) {
  $ComposeFile = Get-DefaultComposeFiles -TargetEnvironment $Environment
}
if (-not $DatabaseName) {
  $DatabaseName = Get-DefaultDatabaseName -TargetEnvironment $Environment
}
if (-not $DatabaseUser) {
  $DatabaseUser = "interview"
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$fileName = "interview-agent-$Environment-$timestamp.sql"
$outputPath = Join-Path $OutputDir $fileName
$containerPath = "/tmp/$fileName"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$composeArgs = New-ComposeArgs -Files $ComposeFile -OptionalEnvFile $EnvFile
$dumpArgs = $composeArgs + @(
  "exec",
  "-T",
  $ServiceName,
  "pg_dump",
  "-U",
  $DatabaseUser,
  "-d",
  $DatabaseName,
  "--clean",
  "--if-exists",
  "--no-owner",
  "--no-privileges",
  "-f",
  $containerPath
)

Write-Host "==> Creating PostgreSQL backup" -ForegroundColor Cyan
Write-Host "Environment: $Environment"
Write-Host "Service: $ServiceName"
Write-Host "Database: $DatabaseName"
Write-Host "Output: $outputPath"

& docker @dumpArgs
if ($LASTEXITCODE -ne 0) {
  throw "pg_dump failed with exit code $LASTEXITCODE"
}

$copyArgs = $composeArgs + @("cp", "${ServiceName}:$containerPath", $outputPath)
& docker @copyArgs
if ($LASTEXITCODE -ne 0) {
  throw "docker compose cp failed with exit code $LASTEXITCODE"
}

$cleanupArgs = $composeArgs + @("exec", "-T", $ServiceName, "rm", "-f", $containerPath)
& docker @cleanupArgs | Out-Null

$item = Get-Item -LiteralPath $outputPath
$hash = Get-FileHash -LiteralPath $outputPath -Algorithm SHA256

Write-Host ""
Write-Host "PostgreSQL backup completed." -ForegroundColor Green
Write-Host "File: $($item.FullName)"
Write-Host "Size bytes: $($item.Length)"
Write-Host "SHA256: $($hash.Hash)"
Write-Host "Created at UTC: $timestamp"
