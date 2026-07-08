param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [ValidateSet("local", "staging")]
  [string]$Environment = "local",
  [string[]]$ComposeFile = @(),
  [string]$EnvFile = "",
  [string]$ServiceName = "postgres",
  [string]$DatabaseName = "",
  [string]$DatabaseUser = "",
  [bool]$RequireConfirmation = $true
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

if (-not (Test-Path -LiteralPath $BackupFile)) {
  throw "Backup file does not exist: $BackupFile"
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

$backup = Get-Item -LiteralPath $BackupFile
$hash = Get-FileHash -LiteralPath $backup.FullName -Algorithm SHA256
$containerPath = "/tmp/restore-$($backup.Name)"

Write-Host "==> PostgreSQL restore requested" -ForegroundColor Yellow
Write-Host "Environment: $Environment"
Write-Host "Service: $ServiceName"
Write-Host "Database: $DatabaseName"
Write-Host "Backup file: $($backup.FullName)"
Write-Host "Size bytes: $($backup.Length)"
Write-Host "SHA256: $($hash.Hash)"
Write-Host ""
Write-Host "This restore can overwrite data in the target database." -ForegroundColor Yellow
Write-Host "Production restore is intentionally not supported by this script; use the documented approval process."

if ($RequireConfirmation) {
  $confirmation = Read-Host "Type RESTORE to continue"
  if ($confirmation -ne "RESTORE") {
    throw "Restore cancelled."
  }
}

$composeArgs = New-ComposeArgs -Files $ComposeFile -OptionalEnvFile $EnvFile

$copyArgs = $composeArgs + @("cp", $backup.FullName, "${ServiceName}:$containerPath")
& docker @copyArgs
if ($LASTEXITCODE -ne 0) {
  throw "docker compose cp failed with exit code $LASTEXITCODE"
}

$restoreArgs = $composeArgs + @(
  "exec",
  "-T",
  $ServiceName,
  "psql",
  "-v",
  "ON_ERROR_STOP=1",
  "-U",
  $DatabaseUser,
  "-d",
  $DatabaseName,
  "-f",
  $containerPath
)
& docker @restoreArgs
if ($LASTEXITCODE -ne 0) {
  throw "psql restore failed with exit code $LASTEXITCODE"
}

$cleanupArgs = $composeArgs + @("exec", "-T", $ServiceName, "rm", "-f", $containerPath)
& docker @cleanupArgs | Out-Null

Write-Host ""
Write-Host "PostgreSQL restore completed." -ForegroundColor Green
Write-Host "Restored file: $($backup.FullName)"
Write-Host "Database: $DatabaseName"
