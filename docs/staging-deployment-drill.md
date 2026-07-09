# Real Staging Deployment Drill

This document defines the repeatable drill for deploying a release candidate to a real staging VPS or cloud server. It turns the staging deployment foundation into an operator-run exercise with evidence.

The drill must not include real production deployment, production secrets, committed server IPs, committed domains, committed API keys, or production user data.

## Drill Goals

- Verify that the staging environment can be deployed from a reviewed commit.
- Verify that PostgreSQL migration can run in the staging topology.
- Verify that smoke tests pass against a real staging endpoint.
- Verify that PostgreSQL backup and backup verification can run.
- Verify that restore is understood and rehearsed without overwriting live staging data.
- Verify that `/metrics` is reachable only through a trusted operator path.
- Verify that privacy data summary, export and deletion APIs can be exercised with a test user.
- Verify that LLM Gateway route and fallback configuration are known.
- Verify that the mock Evaluation Harness has run before changing model routes for beta.
- Verify that incident evidence can be filled if the drill exposes a P0/P1 symptom.

## Prerequisites

- One staging VPS or cloud server.
- Docker and Docker Compose installed.
- Git installed.
- Firewall rules reviewed.
- Staging access address prepared outside git.
- `.env.staging` prepared from `.env.staging.example` outside git.
- Runtime secrets stored outside git.
- PostgreSQL and Redis ports are not publicly exposed.
- `/metrics` is protected by internal networking, VPN, reverse proxy access control or another deployment-layer control.
- Operator has access to `docs/public-beta-readiness.md`, `docs/public-beta-evidence-template.md`, `docs/backup-evidence-template.md`, `docs/incident-evidence-template.md` and `docs/staging-deployment-drill-evidence-template.md`.

## Execution Steps

1. Pull the repository on the staging host.
2. Check out the target commit SHA or release candidate tag.
3. Prepare `.env.staging` from `.env.staging.example`.
4. Confirm secrets are present only in the runtime environment, not in git.
5. Run Compose validation:

```powershell
docker compose --env-file .env.staging -f docker-compose.yml -f docker-compose.staging.yml config --quiet
```

6. Pull or build immutable release images:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml pull
docker compose --env-file .env.staging -f docker-compose.staging.yml build
```

7. Start the stack:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d postgres redis api worker frontend
```

8. Confirm containers are running:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
```

9. Confirm migration status from API logs. The staging API command applies `alembic upgrade head`.
10. Check `/health`.
11. Check `/ready` and confirm DB and Redis are ready.
12. Run staging smoke:

```powershell
.\scripts\staging-smoke.ps1 `
  -BaseUrl "<staging-frontend-url>" `
  -ApiBaseUrl "<staging-api-url>/api"
```

13. Check `/metrics` from a trusted operator path only.
14. Create a PostgreSQL backup:

```powershell
.\scripts\backup-postgres.ps1 `
  -Environment staging `
  -EnvFile .env.staging `
  -OutputDir backups
```

15. Verify the backup:

```powershell
.\scripts\verify-postgres-backup.ps1 `
  -BackupFile ".\backups\<backup-file>.sql" `
  -ExpectedTables users,sessions,questions
```

16. Rehearse restore only into a disposable local database or an explicitly prepared temporary staging database. Do not overwrite the active staging database unless a separate restore approval exists.
17. Verify privacy data summary, export and delete APIs with a test user.
18. Verify LLM Gateway primary and fallback route configuration. Do not paste API keys or prompt text into evidence.
19. Run the mock Evaluation Harness when the release candidate changes model routing, scoring prompts or rubric behavior:

```powershell
.\scripts\run-eval.ps1
```

20. Check worker behavior for queued async jobs if `ASYNC_JOB_BACKEND=redis`.
21. Fill `docs/staging-deployment-drill-evidence-template.md` outside the repository with the real values.
22. Fill or update `docs/public-beta-evidence-template.md` if this drill is a public beta gate input.

## Semi-Automated Drill Check

For static local or CI validation:

```powershell
.\scripts\staging-deployment-drill.ps1 -SkipExternalChecks
```

For a real staging host with URLs:

```powershell
.\scripts\staging-deployment-drill.ps1 `
  -EnvFile .env.staging `
  -FrontendBaseUrl "<staging-frontend-url>" `
  -ApiBaseUrl "<staging-api-url>/api"
```

The script checks required files, Compose config, optional `/health`, optional `/ready`, optional `/metrics`, optional staging smoke and an evidence skeleton. It does not run restore.

## Rollback

Code rollback:

1. Stop new beta invitations.
2. Identify the last known good immutable image tag.
3. Update `.env.staging` image tags outside git.
4. Restart `api`, `worker` and `frontend`.
5. Run `/health`, `/ready` and staging smoke.
6. Record the rollback in release or drill evidence.

Config rollback:

1. Restore the previous `.env.staging` from the operator-managed secret store.
2. Restart affected services.
3. Confirm no secret values are pasted into evidence.

Database restore:

1. Treat restore as a separate approval from code rollback.
2. Verify the backup checksum.
3. Prefer restoring into a temporary database first.
4. Do not overwrite active staging data without explicit approval.
5. Run smoke tests after restore.

Worker handling:

1. Stop the worker before risky migration or restore steps.
2. Resume the worker after DB and Redis readiness are confirmed.
3. Check async job metrics and worker logs.

Redis cleanup:

1. Redis contains rate-limit counters, cache and async queue data.
2. Do not clear Redis during an active drill unless the impact is understood.
3. If Redis must be cleared, record the reason and expected user impact.

## Troubleshooting

API does not start:

- Check `JWT_SECRET_KEY`, `DATABASE_URL`, `AUTH_DEV_CODE_ENABLED`, Redis URL and LLM provider config.
- Check API logs for fail-fast configuration validation errors.

Frontend cannot reach API:

- Check `NEXT_PUBLIC_API_BASE_URL` at build time.
- Check reverse proxy and CORS configuration.

Migration failed:

- Stop the drill.
- Confirm backup exists and checksum is recorded.
- Review Alembic logs before retrying.

Redis not ready:

- Check Redis container health.
- Confirm `REDIS_URL` points to the Compose service name, not a public endpoint.

DB not ready:

- Check Postgres container health, credentials and volume.
- Confirm DB port is not exposed publicly.

Metrics returns 403 or is unreachable:

- Confirm metrics are intentionally protected.
- Use an internal trusted path for the check.
- Do not make `/metrics` public to pass the drill.

LLM provider failed:

- Confirm `LLM_GATEWAY_ENABLED`, primary route and fallback route.
- Confirm provider key is configured outside git.
- Check usage and metrics, not prompt text.

Worker does not consume jobs:

- Check `ASYNC_JOBS_ENABLED`, `ASYNC_JOB_BACKEND=redis`, queue name, Redis readiness and worker logs.

## Completion Criteria

- Compose config passes.
- Staging stack starts.
- `/health` and `/ready` pass.
- Smoke test passes.
- Metrics are accessible from trusted operator path only.
- Backup and verification pass.
- Restore drill is completed against a safe target or explicitly deferred with a reason.
- Privacy and LLM Gateway checks are recorded.
- Incident evidence template is available.
- Public beta readiness receives this drill evidence as an input.
