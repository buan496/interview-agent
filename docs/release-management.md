# Release/CD Management v1

This document defines the Interview Agent release management baseline. It is a release governance and release-candidate evidence process. It does not deploy production servers and does not require production secrets.

## Environment Layers

| Environment | Purpose | Limits |
| --- | --- | --- |
| local | Developer iteration, local Docker Compose, fast validation | May use development auth code and local-only defaults |
| test | Automated CI and deterministic test fixtures | No external LLM, SMS, payment, or production data |
| staging | Production-like rehearsal and manual release validation | Must use production-shaped config, but not real user production data |
| production | Real users and real operational risk | Manual gated release only; no workflow in this repository deploys production directly |

Main branch merge is not a production release. A production release requires a release candidate, evidence review, migration decision, rollback plan, and explicit human approval.

## Release Workflow

GitHub Actions provides `.github/workflows/release.yml`.

It is intentionally manual:

- trigger: `workflow_dispatch`
- input: `target_environment` = `staging` or `production`
- input: `image_tag`
- input: `run_e2e`
- input: `migration_mode` = `check_only` or `apply_manual`

The workflow performs:

- backend compile, lint, and unit tests
- Alembic heads check and upgrade against an ephemeral CI PostgreSQL database
- frontend lint, typecheck, and production build
- optional Playwright E2E
- Docker Compose config validation
- Docker builds for API and frontend candidate images
- release summary generation

It does not:

- deploy production
- apply migrations to staging or production databases
- push images to a registry
- require production secrets
- create or modify infrastructure

For staging release candidates, use `docs/staging-deployment.md` after this workflow succeeds. The workflow validates the staging compose configuration, but it does not SSH into a host and does not start staging services.

## Pre-Release Checklist

- The target commit is on `main` or a reviewed release branch.
- CI is green for Backend, Frontend, Migrations, Compose Config, Docker Build, and Secret Scan.
- `docs/configuration.md` has been checked for the target environment.
- The release candidate workflow has completed successfully.
- For production approval, staging deployment evidence and smoke test results are complete.
- No P0/P1 incident is active for the target environment.
- Alerting rules and incident runbook are reviewed when the release changes metrics, worker behavior, Redis, LLM routing or database migrations.
- The release evidence template has been filled in.
- Database backup evidence is complete when a migration is planned.
- Known risks and rollback plan are documented.
- A human approver has approved the release.

## Configuration Checklist

- `APP_ENV` matches the target environment.
- Production does not use default `JWT_SECRET`.
- Production does not enable `AUTH_DEV_CODE_ENABLED`.
- Production does not use default `AUTH_DEV_CODE=000000`.
- `DATABASE_URL` is configured outside the repository.
- LLM provider, model, timeout, and pricing version are documented.
- If a real LLM provider is enabled, its API key is configured in the runtime secret store.
- Logs and release evidence do not contain secret values, tokens, verification codes, database passwords, full phone numbers, or prompt text.

Staging-specific config:

- `APP_ENV=staging`
- `RATE_LIMIT_BACKEND=redis`
- `CACHE_BACKEND=redis`
- `AUTH_DEV_CODE_ENABLED=false`
- `JWT_SECRET_KEY` supplied outside git
- `DATABASE_URL` and `REDIS_URL` supplied from `.env.staging`
- `NEXT_PUBLIC_API_BASE_URL` points at the staging API URL

## Database Migration Gate

Before release:

- Run `alembic heads` and confirm there is one expected head unless a multi-head migration is intentional.
- Run `alembic upgrade head` against CI and staging databases.
- Review migration files for destructive operations.
- Create and verify a PostgreSQL backup before staging migration rehearsal.
- Back up production before any production migration, with separate approval and encrypted storage.
- Record backup path, file size, SHA256, operator and reason using `docs/backup-evidence-template.md`.
- Confirm rollback strategy before applying production migration.

During release:

- If migration fails, stop the release.
- Do not continue with an app version that expects a schema that was not applied.
- Record the migration revision and result in release evidence.

Rollback:

- Prefer code rollback first when schema is backward compatible.
- Treat database rollback separately from code rollback.
- Do not restore or downgrade production without reviewed backup evidence, approval, and data-loss assessment.

## Docker Image Version Strategy

Allowed image tag examples:

- `interview-agent-api:<git-sha>`
- `interview-agent-frontend:<git-sha>`
- `interview-agent-api:v0.1.0-rc.1`
- `interview-agent-frontend:v0.1.0-rc.1`
- `interview-agent-api:v0.1.0`
- `interview-agent-frontend:v0.1.0`

Release tag examples:

- `v0.1.0-rc.1`
- `v0.1.0`

Rules:

- Do not use `latest` as the only production reference.
- Prefer immutable tags based on git SHA or semantic release tags.
- If GHCR publishing is enabled later, registry push must be a separate explicit release decision.
- The current release candidate workflow builds images locally in CI and does not push them.

## Rollback SOP

1. Declare incident severity and freeze further releases.
2. Locate the release evidence for the deployed version.
3. Use `request_id` from user reports or logs to identify the failing path.
4. Check `/health` and `/ready`.
5. Check structured logs for `http_request`, `http_request_exception`, auth events, session events, report events, and LLM usage events.
6. Check `GET /api/me/usage/summary` or internal usage ledger queries for abnormal LLM cost or failure spikes.
7. If the database schema is compatible, roll back app images to the previous immutable tag.
8. If schema rollback is required, restore from a verified backup or run reviewed downgrade steps only after explicit approval.
9. Run post-rollback smoke checks.
10. Document root cause and prevention follow-ups.

## Hotfix SOP

1. Branch from the deployed commit or current `main`, depending on incident scope.
2. Keep the fix minimal.
3. Run backend tests, frontend checks, E2E, migration checks, Docker build, and secret scan.
4. Create a hotfix release candidate tag, for example `v0.1.1-rc.1`.
5. Fill release evidence with incident context and rollback plan.
6. Require human approval before production rollout.

## Release Evidence Template

Use `docs/release-evidence-template.md` for every staging or production release candidate.

The evidence must include:

- release version
- commit SHA
- target environment
- config checklist
- test results
- migration status
- backup evidence
- Docker image tag
- approver
- rollback plan
- known risks
- post-release smoke results

For an invited beta, also complete [Public Beta Evidence Template](public-beta-evidence-template.md) and review [Public Beta Readiness Checklist](public-beta-readiness.md). A release candidate is not beta-ready until the beta Go / No-Go decision, incident owner, privacy checks, backup evidence and LLM quota/cost checks are recorded.

## Staging Deployment Flow

1. Run the manual release workflow with `target_environment=staging`.
2. Prepare `.env.staging` from `.env.staging.example` outside git.
3. Start staging with `docker compose --env-file .env.staging -f docker-compose.staging.yml up -d`.
4. Before migration rehearsal, create a PostgreSQL backup with `scripts/backup-postgres.ps1` and verify it with `scripts/verify-postgres-backup.ps1`.
5. Confirm `/health`, `/ready` and `/metrics`; readiness should include Redis when Redis-backed rate limit or cache is enabled.
6. Run `scripts/staging-smoke.ps1`.
7. Run `scripts/beta-readiness-check.ps1` when the release candidate is intended for invited beta.
8. Record image tags, backup evidence, migration result, smoke result, metrics availability and observed request id in release evidence.
9. Only after staging evidence is complete should production approval be considered.

## Public Beta Gate

Before inviting beta users:

1. Complete `docs/public-beta-readiness.md`.
2. Fill `docs/public-beta-evidence-template.md` for the target environment.
3. Confirm no beta forbidden item applies.
4. Confirm the release candidate has staging smoke evidence and backup evidence.
5. Confirm privacy export/delete, LLM Gateway fallback, quotas, rate limits, Redis readiness and incident ownership.

This gate does not deploy production, does not enable payment, and does not integrate external alerting services.

## Troubleshooting After Release

- Ask for the `X-Request-ID` from user-visible errors or support reports.
- Search backend structured logs by `request_id`.
- For 500 errors, inspect `http_request_exception`.
- For auth failures, inspect masked `auth.login` and `auth.request_code` events.
- For LLM cost or failure anomalies, inspect `llm_usage_records` and `GET /api/me/usage/summary`.
- For aggregate symptoms, inspect `/metrics` for HTTP 5xx/latency, rate-limit/quota refusals, dependency readiness and LLM failure or token spikes.
- For P0/P1 symptoms, open `docs/incident-evidence-template.md` and follow `docs/incident-runbook.md`.
- For migrations, confirm backup evidence before any restore decision.
- Never paste tokens, secrets, full phone numbers, prompt text, or user answer text into release notes.

## Current Non-Goals

- No real production deployment.
- No production secrets required in GitHub Actions.
- No Kubernetes.
- No external CD platform.
- No registry push from the release candidate workflow.
- No automated production database migration.
- No automated production database backup or restore.
