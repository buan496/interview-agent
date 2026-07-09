# Release Evidence Template

Use this template for every staging or production release candidate.

## Release Identity

- Release version:
- Release candidate:
- Commit SHA:
- Source branch:
- Pull request:
- Target environment:
- Release owner:
- Release approver:
- Release window:

## Configuration Checklist

- [ ] `APP_ENV` matches target environment.
- [ ] Staging uses `.env.staging` generated from `.env.staging.example`.
- [ ] Staging uses `RATE_LIMIT_BACKEND=redis` and `CACHE_BACKEND=redis`.
- [ ] Staging has `AUTH_DEV_CODE_ENABLED=false`.
- [ ] Production does not use default JWT secret.
- [ ] Production does not use default development verification code.
- [ ] Production has `AUTH_DEV_CODE_ENABLED=false`.
- [ ] `DATABASE_URL` is configured outside the repository.
- [ ] LLM provider, model, timeout, and pricing version are confirmed.
- [ ] Required LLM API key is configured for real provider usage.
- [ ] Logs and evidence contain no secret values, tokens, verification codes, database passwords, full phone numbers, prompt text, or user answer text.

## Test Results

| Check | Result | Evidence |
| --- | --- | --- |
| Backend unit tests |  |  |
| Backend lint |  |  |
| Backend compile |  |  |
| Frontend lint |  |  |
| Frontend typecheck |  |  |
| Frontend build |  |  |
| Playwright E2E |  |  |
| Visual smoke |  |  |
| Docker Compose config |  |  |
| Staging Docker Compose config |  |  |
| Docker build |  |  |
| Secret scan |  |  |
| Public beta readiness check |  |  |

## Migration Status

- Alembic current revision:
- Alembic target head:
- Migration mode:
- Pre-migration backup required: yes / no
- Pre-migration backup evidence:
- Backup file:
- Backup SHA256:
- Staging migration result:
- Staging smoke result:
- Staging metrics result:
- Staging observed request_id:
- Production backup completed:
- Production backup evidence:
- Production migration approved by:
- Production migration result:
- Notes:

## Docker Image Tags

- API image:
- Frontend image:
- Immutable image tag:
- Registry push performed: yes / no
- Production deploy performed: yes / no

## Release Summary

- User-visible changes:
- Operational changes:
- Config changes:
- Database changes:
- Known risks:

## Alerting and Incident Readiness

- Alert rules reviewed:
- Active P0/P1 incidents before release:
- Staging metrics checked:
- P0/P1 incident freeze approved if applicable:
- Incident runbook link:
- Incident evidence record if release is related to an incident:

## Public Beta Readiness

- Public beta checklist reviewed:
- Public beta evidence link:
- Beta target users count:
- Beta operator:
- Beta incident owner:
- Beta Go / No-Go decision:
- Beta known risks:
- Beta privacy export/delete check:
- Beta LLM quota and budget check:
- Beta backup evidence:
- Beta forbidden items reviewed:

## Rollback Plan

- Previous API image:
- Previous frontend image:
- Code rollback command or process:
- Database rollback strategy:
- Backup location:
- Backup checksum:
- Restore approval required:
- Rollback owner:
- Rollback approval required:

## Post-Release Smoke

- `/health`:
- `/ready`:
- `/metrics`:
- Login smoke:
- `/practice` smoke:
- `/session/{id}` smoke:
- `/report/{id}` smoke:
- `/wrong-book` smoke:
- `/history` smoke:
- `/ability` smoke:
- Staging smoke script:
- Observed request_id for smoke:

## Incident Follow-Up

- Any errors observed:
- Request IDs:
- LLM usage anomaly:
- Cost anomaly:
- Follow-up issues or PRs:
