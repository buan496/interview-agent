param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [long]$MinBytes = 1,
  [string[]]$ExpectedTables = @()
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupFile)) {
  throw "Backup file does not exist: $BackupFile"
}

$backup = Get-Item -LiteralPath $BackupFile
if ($backup.Length -lt $MinBytes) {
  throw "Backup file is too small. Size=$($backup.Length), MinBytes=$MinBytes"
}

$hash = Get-FileHash -LiteralPath $backup.FullName -Algorithm SHA256

foreach ($table in $ExpectedTables) {
  $escaped = [regex]::Escape($table)
  $pattern = "(?i)(CREATE TABLE|COPY|ALTER TABLE).*$escaped"
  if (-not (Select-String -LiteralPath $backup.FullName -Pattern $pattern -Quiet)) {
    throw "Backup file does not contain expected table marker: $table"
  }
}

Write-Host "PostgreSQL backup verification passed." -ForegroundColor Green
Write-Host "File: $($backup.FullName)"
Write-Host "Size bytes: $($backup.Length)"
Write-Host "SHA256: $($hash.Hash)"
if ($ExpectedTables.Count -gt 0) {
  Write-Host "Expected tables checked: $($ExpectedTables -join ', ')"
}
