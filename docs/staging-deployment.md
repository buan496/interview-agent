# Staging Deployment Foundation

This document defines the staging deployment baseline for Interview Agent. Staging is a production-like rehearsal environment for release candidates. It is not production, must not contain production user data, and must not use real production secrets.

## Goals

- Validate release candidates before production approval.
- Exercise production-shaped configuration from PR #36.
- Exercise the release candidate process from PR #37.
- Exercise Redis-backed rate limit and cache readiness from PR #44.
- Provide repeatable smoke evidence for release records.

## Environment Model

Staging contains:

- `frontend`: Next.js production build.
- `api`: FastAPI backend.
- `worker`: lightweight async job worker using the same backend image.
- `postgres`: PostgreSQL with pgvector.
- `redis`: Redis for shared rate-limit counters, cache foundation and async job queue.
- `/metrics`: Prometheus-compatible backend metrics endpoint for staging operator checks or internal scrape jobs.

Staging deliberately excludes:

- Kubernetes.
- Real production deployment.
- Production secrets.
- Production user data.
- Public database or Redis ports by default.
- External CD platforms.

## Files

- `docker-compose.staging.yml`: staging compose topology.
- `.env.staging.example`: staging environment template.
- `scripts/staging-smoke.ps1`: staging smoke checks.
- `scripts/backup-postgres.ps1`: staging PostgreSQL backup.
- `scripts/restore-postgres.ps1`: staging/local PostgreSQL restore.
- `scripts/verify-postgres-backup.ps1`: backup artifact verification.
- `scripts/staging-deployment-drill.ps1`: static and optional live staging drill checks.
- `docs/release-evidence-template.md`: evidence record after release candidate validation.
- `docs/backup-evidence-template.md`: backup artifact evidence.
- `docs/staging-deployment-drill.md`: real staging drill SOP.
- `docs/staging-deployment-drill-evidence-template.md`: staging drill evidence template.

## Prepare Environment Variables

Create a local or server-side `.env.staging` from the template:

```powershell
Copy-Item .env.staging.example .env.staging
```

Replace every `__CHANGE_ME__` value before running staging.

Required staging values:

- `IMAGE_TAG`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ASYNC_JOB_BACKEND=redis`
- `ASYNC_JOB_QUEUE_NAME`
- `NEXT_PUBLIC_API_BASE_URL`
- `CORS_ORIGINS`

Optional but recommended:

- `DEEPSEEK_API_KEY`
- `SMS_PROVIDER_KEY`
- `ADMIN_PHONES`
- `WHISPER_API_KEY`

Staging auth should keep:

```text
AUTH_DEV_CODE_ENABLED=false
AUTH_DEV_CODE=__DISABLED_IN_STAGING__
```

## Start Staging

Build and start the staging stack:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build
```

Use immutable release tags when the images are available:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml pull
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d
```

Do not use `latest` as the only staging image reference.

## Migration Gate

The staging `api` command runs:

```text
alembic upgrade head
```

Before production approval:

1. Confirm release workflow migration gate passed.
2. Create a staging PostgreSQL backup before applying or rehearsing migration.
3. Verify backup checksum and file size.
4. Confirm staging boot applied migrations successfully.
5. Record backup evidence and Alembic head in release evidence.
6. Review rollback strategy before production migration.

If staging backup, verification, or migration fails, stop the release candidate.

Example staging backup:

```powershell
.\scripts\backup-postgres.ps1 `
  -Environment staging `
  -EnvFile .env.staging `
  -OutputDir backups
```

Verify:

```powershell
.\scripts\verify-postgres-backup.ps1 `
  -BackupFile .\backups\interview-agent-staging-20260708T120000Z.sql `
  -ExpectedTables users,sessions,questions
```

## Health and Readiness

Check API liveness:

```powershell
Invoke-WebRequest http://localhost:8000/health
```

Check readiness:

```powershell
Invoke-WebRequest http://localhost:8000/ready
```

Expected readiness in staging:

```json
{"status":"ready","db":"ok","redis":"ok"}
```

If `redis` is not `ok`, inspect Redis container health and backend logs before continuing.

When `ASYNC_JOB_BACKEND=redis`, `/ready` depends on Redis because async jobs need the queue backend. Staging should run both `api` and `worker` services:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml ps api worker redis
```

Check metrics from a trusted operator path:

```powershell
Invoke-WebRequest http://localhost:8000/metrics
```

Expected staging metrics include HTTP counters, request duration histograms, dependency readiness gauges, rate-limit/quota counters and LLM usage counters. Do not expose `/metrics` to the public internet.

Before approving a release candidate, also check that no P0/P1 incident is active for the candidate environment. Use `docs/alerting.md` for severity definitions and `docs/incident-runbook.md` if staging metrics show 5xx, dependency, LLM, quota or worker symptoms.

If alert rules are being reviewed locally, run:

```powershell
.\scripts\check-alert-rules.ps1
```

## Smoke Test

Async job smoke can be exercised after login by calling:

```text
POST /api/me/memories/refresh-async
GET  /api/me/jobs/{job_id}
```

The expected initial response is `status=queued`. The worker should later move the job to `succeeded` or terminal `failed` after retries.

Run:

```powershell
.\scripts\staging-smoke.ps1 `
  -BaseUrl "http://localhost:3000" `
  -ApiBaseUrl "http://localhost:8000/api"
```

The smoke test checks:

- `/health`
- `/ready`
- `/metrics` endpoint availability when metrics are enabled
- `X-Request-ID` response header
- frontend `/login`
- `/api/auth/request-code` does not expose `development_code` or `000000`

Record the observed request id in release evidence.

For a release candidate that will be used by invited beta users, run the local beta readiness check after staging smoke:

```powershell
.\scripts\beta-readiness-check.ps1
```

For the first real staging host or any release candidate that may become a public beta candidate, also run the staging deployment drill:

```powershell
.\scripts\staging-deployment-drill.ps1 `
  -EnvFile .env.staging `
  -FrontendBaseUrl https://staging.example.com `
  -ApiBaseUrl https://staging.example.com/api
```

CI should only run the static form:

```powershell
.\scripts\staging-deployment-drill.ps1 -SkipExternalChecks -SkipBackup
```

The drill links deployment, migration, smoke, backup, restore-safety, metrics, privacy, LLM Gateway and incident evidence checks. Restore is never executed by the drill script.

If a staging endpoint is already running, optional URL checks can be added:

```powershell
.\scripts\beta-readiness-check.ps1 `
  -ApiBaseUrl https://staging.example.com `
  -FrontendBaseUrl https://staging.example.com
```

## Release Evidence

After staging validation, update `docs/release-evidence-template.md` fields in the actual release record:

- target environment: `staging`
- image tags
- backup file, size and SHA256
- migration result
- smoke test result
- observed request id
- metrics and active incident check
- known risks
- rollback plan

Production approval should not happen until staging evidence is complete.

Public beta approval should not happen until `docs/public-beta-evidence-template.md` is filled and the Go / No-Go decision in `docs/public-beta-readiness.md` is explicitly recorded.

Public beta approval also requires at least one completed real staging drill recorded with `docs/staging-deployment-drill-evidence-template.md`.

## Logs and Troubleshooting

Useful commands:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
docker compose --env-file .env.staging -f docker-compose.staging.yml logs api
docker compose --env-file .env.staging -f docker-compose.staging.yml logs redis
docker compose --env-file .env.staging -f docker-compose.staging.yml logs frontend
```

Troubleshooting flow:

1. Start with `X-Request-ID`.
2. Search API structured logs for that request id.
3. If `/ready` fails, check database and Redis health.
4. If auth smoke exposes a development code, stop the release and fix config.
5. If migration fails, stop the release and do not proceed to production.
6. If LLM failures spike, inspect `llm_usage_records` and provider config.
7. If P0/P1 alerts are active, pause release approval and open an incident record.

Never paste secrets, full phone numbers, prompt text, answer text, database passwords or provider keys into release evidence.

## Rollback

If staging validation fails:

1. Record the failing request id and logs.
2. Stop the candidate:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml down
```

3. Re-run the previous known-good immutable image tag.
4. Re-run `scripts/staging-smoke.ps1`.
5. If database restore is required, use `scripts/restore-postgres.ps1` only after confirming the target environment and backup checksum.
6. Attach failure notes to the release evidence.

## Common Failures

- `api` exits on startup: check `JWT_SECRET_KEY`, `DATABASE_URL`, `AUTH_DEV_CODE_ENABLED`, and LLM provider config.
- `/ready` returns 503: check database or Redis health.
- frontend calls the wrong API: check `NEXT_PUBLIC_API_BASE_URL` at build time.
- auth request-code returns `development_code`: staging env is using development auth and must be fixed.
- migrations fail: stop release and review Alembic revision history.
- backup verification fails: discard the artifact and create a new backup before migration.
- beta readiness check fails: stop the invite process and fix the missing document, script, config placeholder or forbidden-item evidence.

## Production Boundary

Do not reuse staging as production. Production needs its own secrets, data, encrypted backups, release evidence, migration approval and rollback plan.
