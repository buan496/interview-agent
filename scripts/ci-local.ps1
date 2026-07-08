param(
  [switch]$SkipDocker,
  [switch]$SkipE2E,
  [switch]$SkipSecretScan
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Command
  )

  Write-Host ""
  Write-Host "==> $Name" -ForegroundColor Cyan
  & $Command
}

Invoke-Step "Backend lint" {
  Push-Location "$root\backend"
  try {
    ruff check app tests
  } finally {
    Pop-Location
  }
}

Invoke-Step "Backend compile" {
  Push-Location "$root\backend"
  try {
    python -m compileall app tests alembic
  } finally {
    Pop-Location
  }
}

Invoke-Step "Backend unit tests" {
  Push-Location "$root\backend"
  try {
    python -m unittest discover -s tests -p "test_*.py" -v
  } finally {
    Pop-Location
  }
}

Invoke-Step "Frontend lint" {
  Push-Location "$root\frontend"
  try {
    npm run lint
  } finally {
    Pop-Location
  }
}

Invoke-Step "Frontend typecheck" {
  Push-Location "$root\frontend"
  try {
    npm run typecheck
  } finally {
    Pop-Location
  }
}

Invoke-Step "Frontend build" {
  Push-Location "$root\frontend"
  try {
    $env:NEXT_TELEMETRY_DISABLED = "1"
    npm run build
  } finally {
    Pop-Location
  }
}

if (-not $SkipE2E) {
  Invoke-Step "Frontend e2e tests" {
    Push-Location "$root\frontend"
    try {
      $env:NEXT_TELEMETRY_DISABLED = "1"
      npm run test:e2e
    } finally {
      Pop-Location
    }
  }
}

Invoke-Step "Docker Compose config" {
  Push-Location $root
  try {
    docker compose -p interview-agent config --quiet
  } finally {
    Pop-Location
  }
}

Invoke-Step "Staging Docker Compose config" {
  Push-Location $root
  try {
    docker compose -p interview-agent-staging -f docker-compose.yml -f docker-compose.staging.yml config --quiet
  } finally {
    Pop-Location
  }
}

if (-not $SkipSecretScan) {
  Invoke-Step "Secret scan" {
    Push-Location $root
    try {
      docker run --rm -v "${PWD}:/repo" zricethezav/gitleaks:latest git /repo --redact
    } finally {
      Pop-Location
    }
  }
}

if (-not $SkipDocker) {
  Invoke-Step "Backend Docker build" {
    Push-Location $root
    try {
      docker build -f backend\Dockerfile -t interview-agent-api:ci .
    } finally {
      Pop-Location
    }
  }

  Invoke-Step "Frontend Docker build" {
    Push-Location $root
    try {
      docker build -f frontend\Dockerfile --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api -t interview-agent-frontend:ci .
    } finally {
      Pop-Location
    }
  }
}
