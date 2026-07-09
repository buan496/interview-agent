# Production Configuration Governance

This document describes Interview Agent configuration governance v1. The goal is local settings-layer governance without Vault, Apollo, Nacos, Kubernetes ConfigMap, or any external configuration center.

## Configuration Groups

App config:

- `APP_ENV` / `ENVIRONMENT`
- `SERVICE_NAME` / `APP_NAME`
- `API_PREFIX`
- `CORS_ORIGINS`

Database / infrastructure config:

- `DATABASE_URL`
- `REDIS_URL`
- `REDIS_CONNECT_TIMEOUT_SECONDS`
- `REDIS_SOCKET_TIMEOUT_SECONDS`

Auth config:

- `JWT_SECRET_KEY` / `TOKEN_SECRET` / `JWT_SECRET`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `SMS_PROVIDER_KEY`

Development auth config:

- `AUTH_DEV_CODE_ENABLED`
- `AUTH_DEV_CODE`

Admin config:

- `ADMIN_PHONES`

RBAC v1 uses `users.role` as the primary admin authorization source. `ADMIN_PHONES` is retained as a bootstrap/fallback mechanism for local development and early production setup, not as the long-term permission model.

LLM config:

- `LLM_PROVIDER`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_GATEWAY_ENABLED`
- `LLM_DEFAULT_PROVIDER`
- `LLM_DEFAULT_MODEL`
- `LLM_FALLBACK_ENABLED`
- `LLM_FALLBACK_PROVIDER`
- `LLM_FALLBACK_MODEL`
- `LLM_ROUTE_INTERVIEW_SCORING`
- `LLM_ROUTE_REPORT_SUMMARY`
- `LLM_ROUTE_MEMORY_REFRESH`
- `LLM_ROUTE_RUBRIC_VALIDATION`
- `LLM_MAX_RETRIES`
- `LLM_PRICING_VERSION`

Usage metering config:

- `LLM_USAGE_METERING_ENABLED`

Rate limit / cache backend config:

- `RATE_LIMIT_BACKEND`
- `REDIS_RATE_LIMIT_PREFIX`
- `CACHE_BACKEND`
- `CACHE_PREFIX`

Async job queue config:

- `ASYNC_JOBS_ENABLED`
- `ASYNC_JOB_BACKEND`
- `ASYNC_JOB_QUEUE_NAME`
- `ASYNC_JOB_MAX_ATTEMPTS`
- `ASYNC_JOB_WORKER_POLL_SECONDS`

Observability config:

- `LOG_LEVEL`
- `LOG_FORMAT`
- `REQUEST_ID_HEADER`
- `METRICS_ENABLED`
- `METRICS_PATH`
- `METRICS_INCLUDE_READY_GAUGES`
- `METRICS_PROTECT_IN_PRODUCTION`

## Local Development

Local development can use the defaults in `.env.example`:

- `APP_ENV=development`
- `AUTH_DEV_CODE_ENABLED=true`
- `AUTH_DEV_CODE=000000`
- `JWT_SECRET=local-dev-only-change-me`
- empty `DEEPSEEK_API_KEY`, which allows the current LLM fallback path to keep the product flow runnable

These defaults are intentionally local-only and must not be used in production.

## Test Environment

Tests may use stable development-style configuration so auth and E2E flows are deterministic. Test fixtures should avoid real provider keys and external services.

## Staging Environment

Staging is configured through `.env.staging`, created from `.env.staging.example`, and deployed with `docker-compose.staging.yml`.

Staging should use production-shaped settings without production user data:

- `APP_ENV=staging`
- `AUTH_DEV_CODE_ENABLED=false`
- `RATE_LIMIT_BACKEND=redis`
- `CACHE_BACKEND=redis`
- `ASYNC_JOB_BACKEND=redis`
- `DATABASE_URL` points at the staging PostgreSQL service
- `REDIS_URL` points at the staging Redis service
- `JWT_SECRET_KEY` is supplied outside git
- `NEXT_PUBLIC_API_BASE_URL` points at the staging API URL
- `CORS_ORIGINS` points at the staging frontend origin

Staging may leave `DEEPSEEK_API_KEY` empty to use gateway fallback behavior for release rehearsal, but the release evidence must record whether the real provider was configured.

## Production Requirements

Production fail-fast validation is implemented in `Settings.validate_production_config()` and is executed during `backend/app/main.py` import before the FastAPI app starts.

Production rejects:

- default `JWT_SECRET_KEY` / `TOKEN_SECRET` / `JWT_SECRET`
- default `AUTH_DEV_CODE=000000`
- `AUTH_DEV_CODE_ENABLED=true`
- `RATE_LIMIT_ENABLED=false`
- `RATE_LIMIT_ENABLED=true` with `RATE_LIMIT_BACKEND=memory`
- `RATE_LIMIT_BACKEND=redis` without `REDIS_URL`
- `CACHE_BACKEND=redis` without `REDIS_URL`
- `ASYNC_JOBS_ENABLED=true` with `ASYNC_JOB_BACKEND=memory`
- `ASYNC_JOB_BACKEND=redis` without `REDIS_URL`
- missing `DATABASE_URL`
- non-positive `ACCESS_TOKEN_EXPIRE_MINUTES`
- missing `LLM_PRICING_VERSION`
- missing `DEEPSEEK_API_KEY` when a real production LLM provider or gateway route is enabled

`ADMIN_PHONES` can be empty. That is not fatal. Admin access can still be granted by setting `users.role='admin'`. If configured, `ADMIN_PHONES` only grants fallback admin access for bootstrap users.

## Sanitized Config Summary

`Settings.sanitized_config_summary()` provides a startup-safe config summary. It follows these rules:

- secrets, tokens, API keys and verification codes are never printed
- `DATABASE_URL` and `REDIS_URL` passwords are masked
- admin phone numbers are masked, for example `138****0000`
- key presence is represented as `configured=true/false`
- `AUTH_DEV_CODE` is never included

The app logs this summary as `config.loaded` after observability is installed.

## LLM Gateway Configuration

PR #49 adds backend LLM Gateway configuration:

- `LLM_GATEWAY_ENABLED=true`: routes model calls through the gateway.
- `LLM_DEFAULT_PROVIDER` and `LLM_DEFAULT_MODEL`: default route when a feature-specific route is empty.
- `LLM_FALLBACK_ENABLED=true`: enables fallback provider attempts.
- `LLM_FALLBACK_PROVIDER` and `LLM_FALLBACK_MODEL`: fallback route, normally `mock/local-fallback` for local and staging resilience.
- `LLM_ROUTE_INTERVIEW_SCORING`: route for answer evaluation.
- `LLM_ROUTE_REPORT_SUMMARY`: reserved route for future report summarization.
- `LLM_ROUTE_MEMORY_REFRESH`: reserved route for future LLM-assisted memory extraction.
- `LLM_ROUTE_RUBRIC_VALIDATION`: reserved route for future rubric validation.
- `LLM_MAX_RETRIES`: bounded retry count per route.

Routes use `provider/model`, for example `deepseek/deepseek-chat` or `mock/local-fallback`. Production fail-fast validation treats any real provider route as requiring the corresponding API key. Config summaries show route names and whether keys are configured, but never print API key values.

## Metrics Configuration

PR #47 adds Prometheus-compatible metrics configuration:

- `METRICS_ENABLED=true`: enables the `/metrics` endpoint.
- `METRICS_PATH=/metrics`: controls the endpoint path and must start with `/`.
- `METRICS_INCLUDE_READY_GAUGES=true`: lets `/ready` update dependency gauges for database and Redis.
- `METRICS_PROTECT_IN_PRODUCTION=true`: prevents direct production access to the metrics endpoint by returning 403.

Local and test environments can read `/metrics` directly. Staging should expose it only to trusted operators or scrape jobs. Production should keep it behind an internal network, sidecar, gateway allowlist or equivalent deployment-level protection. Metrics must not contain request ids, user ids, session ids, phone numbers, tokens, secrets, verification codes, prompt text, completion text or answer text.

## Rate Limit and Quota Configuration

PR #39 adds rate limit and quota configuration:

- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_BACKEND`
- `REDIS_RATE_LIMIT_PREFIX`
- `LOGIN_RATE_LIMIT_PER_MINUTE`
- `AUTH_PHONE_RATE_LIMIT_PER_HOUR`
- `ANSWER_SUBMIT_RATE_LIMIT_PER_MINUTE`
- `LLM_DAILY_TOKEN_QUOTA`
- `LLM_MONTHLY_TOKEN_QUOTA`
- `LLM_DAILY_CALL_QUOTA`

Development defaults are intentionally broad enough for local E2E and demos. Production must keep `RATE_LIMIT_ENABLED=true`.

PR #44 upgrades request rate limits to a configurable backend:

- `RATE_LIMIT_BACKEND=memory`: local/test default. It is deterministic and has no external dependency, but only protects one backend process.
- `RATE_LIMIT_BACKEND=redis`: staging/production default. It uses Redis counters with TTL so multiple backend processes share the same auth and answer-submit buckets.

Production rejects `RATE_LIMIT_BACKEND=memory` when `RATE_LIMIT_ENABLED=true`. Redis-backed limits require `REDIS_URL`, `REDIS_RATE_LIMIT_PREFIX`, and positive Redis timeout values. Redis keys use hashed request identities, so raw phone numbers and bearer tokens are not written into limiter keys.

LLM quota checks use `llm_usage_records` and are scoped by `current_user.id`. Quotas are internal cost-control guardrails only. They are not payment, subscription, billing, or plan enforcement.

## Cache Foundation Configuration

PR #44 also adds the cache backend switch:

- `CACHE_BACKEND=memory`
- `CACHE_BACKEND=redis`
- `CACHE_PREFIX`

This is only a foundation switch and prefix. The PR does not add a broad application cache, distributed lock, task queue or Agent Memory. If `CACHE_BACKEND=redis`, `/ready` checks Redis connectivity.

## Async Job Queue Configuration

PR #50 adds the async job backend switch:

- `ASYNC_JOBS_ENABLED=true`
- `ASYNC_JOB_BACKEND=memory`: local/test default. It is process-local and deterministic for tests.
- `ASYNC_JOB_BACKEND=redis`: staging/production backend. It stores job ids in a Redis list so API and worker processes can communicate.
- `ASYNC_JOB_QUEUE_NAME`: Redis list key for queued job ids.
- `ASYNC_JOB_MAX_ATTEMPTS`: default retry limit for new jobs.
- `ASYNC_JOB_WORKER_POLL_SECONDS`: worker loop sleep interval when no job is available.

Production rejects `ASYNC_JOB_BACKEND=memory` when async jobs are enabled. If `ASYNC_JOB_BACKEND=redis`, `/ready` checks Redis connectivity. Job payloads must not contain raw answer text, prompt text, completion text, tokens, secrets, verification codes or full phone numbers.

## Backup and Restore Configuration

Backup scripts use the same Compose and environment files as the target environment:

- local: `docker-compose.yml`
- staging: `docker-compose.staging.yml` plus `.env.staging`

PostgreSQL backup and restore parameters can be overridden through script arguments for service name, database name and database user. The scripts do not print database passwords and do not support production by default. Production backup configuration must be managed outside the repository with encrypted storage and human approval.

Backup artifacts belong in `backups/`, which is ignored by git.

## Troubleshooting Startup Failures

If the app fails during production startup:

1. Read the config error message for missing or unsafe variable names.
2. Do not paste secret values into logs, tickets, PR comments or screenshots.
3. Compare the environment against `.env.example` and this document.
4. Confirm `APP_ENV=production` is intentional.
5. Confirm real provider mode has `DEEPSEEK_API_KEY`.
6. Confirm development-only auth is disabled.

## Change Checklist

When adding a new config variable:

- add it to `backend/app/settings.py`
- add production validation if it can break startup or security
- add it to `sanitized_config_summary()` without exposing sensitive values
- add or update tests in `backend/tests`
- update `.env.example`
- update this document
- update Docker Compose only if the variable is needed by local development

## Current Limitations

- No external configuration center.
- No runtime dynamic config reload.
- No tenant-specific config.
- No real SMS provider integration.
- Release/CD promotion is documented in `docs/release-management.md`, but this repository still does not deploy production directly.

## Release Configuration Relationship

Release candidates must use this document as the configuration checklist source.

- local and test may use deterministic development-style settings
- staging should use production-shaped settings without real production user data
- production must pass `Settings.validate_production_config()` before app startup
- production secrets must be supplied outside the repository
- release evidence must record whether each required config group was checked

The release workflow builds and validates release candidates, but it does not inject production secrets and does not deploy production.

For staging deployment details, see `docs/staging-deployment.md`. Staging release candidates should run `scripts/staging-smoke.ps1` and record the observed request id in release evidence.
