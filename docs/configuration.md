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

Auth config:

- `JWT_SECRET_KEY` / `TOKEN_SECRET` / `JWT_SECRET`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `SMS_PROVIDER_KEY`

Development auth config:

- `AUTH_DEV_CODE_ENABLED`
- `AUTH_DEV_CODE`

Admin config:

- `ADMIN_PHONES`

LLM config:

- `LLM_PROVIDER`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_PRICING_VERSION`

Usage metering config:

- `LLM_USAGE_METERING_ENABLED`

Observability config:

- `LOG_LEVEL`
- `LOG_FORMAT`
- `REQUEST_ID_HEADER`

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

## Production Requirements

Production fail-fast validation is implemented in `Settings.validate_production_config()` and is executed during `backend/app/main.py` import before the FastAPI app starts.

Production rejects:

- default `JWT_SECRET_KEY` / `TOKEN_SECRET` / `JWT_SECRET`
- default `AUTH_DEV_CODE=000000`
- `AUTH_DEV_CODE_ENABLED=true`
- missing `DATABASE_URL`
- non-positive `ACCESS_TOKEN_EXPIRE_MINUTES`
- missing `LLM_PRICING_VERSION`
- missing `DEEPSEEK_API_KEY` when a real production LLM provider is enabled

`ADMIN_PHONES` can be empty. That is not fatal, but it means no phone is allowed through the current v1 admin allowlist.

## Sanitized Config Summary

`Settings.sanitized_config_summary()` provides a startup-safe config summary. It follows these rules:

- secrets, tokens, API keys and verification codes are never printed
- `DATABASE_URL` and `REDIS_URL` passwords are masked
- admin phone numbers are masked, for example `138****0000`
- key presence is represented as `configured=true/false`
- `AUTH_DEV_CODE` is never included

The app logs this summary as `config.loaded` after observability is installed.

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
