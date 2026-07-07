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

## Pre-Release Checklist

- The target commit is on `main` or a reviewed release branch.
- CI is green for Backend, Frontend, Migrations, Compose Config, Docker Build, and Secret Scan.
- `docs/configuration.md` has been checked for the target environment.
- The release candidate workflow has completed successfully.
- The release evidence template has been filled in.
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

## Database Migration Gate

Before release:

- Run `alembic heads` and confirm there is one expected head unless a multi-head migration is intentional.
- Run `alembic upgrade head` against CI and staging databases.
- Review migration files for destructive operations.
- Back up production before any production migration.
- Confirm rollback strategy before applying production migration.

During release:

- If migration fails, stop the release.
- Do not continue with an app version that expects a schema that was not applied.
- Record the migration revision and result in release evidence.

Rollback:

- Prefer code rollback first when schema is backward compatible.
- Treat database rollback separately from code rollback.
- Do not run downgrade on production without a reviewed backup and data-loss assessment.

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
8. If schema rollback is required, restore from backup or run reviewed downgrade steps only after explicit approval.
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
- Docker image tag
- approver
- rollback plan
- known risks
- post-release smoke results

## Troubleshooting After Release

- Ask for the `X-Request-ID` from user-visible errors or support reports.
- Search backend structured logs by `request_id`.
- For 500 errors, inspect `http_request_exception`.
- For auth failures, inspect masked `auth.login` and `auth.request_code` events.
- For LLM cost or failure anomalies, inspect `llm_usage_records` and `GET /api/me/usage/summary`.
- Never paste tokens, secrets, full phone numbers, prompt text, or user answer text into release notes.

## Current Non-Goals

- No real production deployment.
- No production secrets required in GitHub Actions.
- No Kubernetes.
- No external CD platform.
- No registry push from the release candidate workflow.
- No automated production database migration.
