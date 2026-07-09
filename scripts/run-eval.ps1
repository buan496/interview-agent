param(
  [string]$Dataset = "evals\datasets\interview_scoring_smoke.jsonl",
  [string]$Feature = "interview_scoring",
  [string]$Provider = "mock",
  [string]$Model = "local-eval",
  [string]$OutputDir = "evals\results",
  [switch]$UseRealProvider
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$datasetPath = Join-Path $root $Dataset
$outputPath = Join-Path $root $OutputDir

Push-Location (Join-Path $root "backend")
try {
  $args = @(
    "-m", "app.eval_runner",
    "run",
    "--dataset", $datasetPath,
    "--feature", $Feature,
    "--provider", $Provider,
    "--model", $Model,
    "--output-dir", $outputPath
  )
  if ($UseRealProvider) {
    $args += "--use-real-provider"
  }
  python @args
} finally {
  Pop-Location
}
