# Public Beta Readiness Checklist

This document defines the readiness gate for a small invited public beta of Interview Agent. It is meant for 5 to 10 real users, not for open public traffic or enterprise customers.

Public beta is still an operator-assisted trial. It does not promise SLA, does not enable paid plans, does not open enterprise tenancy, and does not replace a production launch review.

## Beta Definition

Public beta v1 means:

- 5 to 10 invited users.
- Non-public, low-volume access.
- Manual operator intervention is allowed.
- No SLA commitment.
- No enterprise customer onboarding.
- No real payment or subscription workflow.
- No production data migration without release, backup and incident evidence.
- No external alerting service requirement.

Environment boundaries:

| Environment | Purpose | Beta rule |
| --- | --- | --- |
| local | Developer checks and deterministic tests | Not used by beta users |
| test | CI and mocked fixtures | No real users or real secrets |
| staging | Release candidate rehearsal and beta candidate validation | Must be production-shaped and secret-backed outside git |
| beta | Small invited-user runtime | Must pass this checklist before users are invited |
| production | Public/paid/enterprise service | Not completed by this repository yet |

## Beta Admission Criteria

Product readiness:

- [ ] Login, practice, mock interview, session answer, report, history, ability profile and wrong-book paths have been smoke tested.
- [ ] Admin-only question/rubric workflows are not exposed to ordinary users.
- [ ] Test-user onboarding instructions are ready.
- [ ] Known product limitations are written down for invited users.

Backend readiness:

- [ ] Backend unit tests pass.
- [ ] Alembic migration check passes.
- [ ] `/health` returns healthy.
- [ ] `/ready` returns ready.
- [ ] Redis readiness is included when Redis-backed rate limit/cache/async jobs are enabled.
- [ ] Rate limit and quota controls are enabled.

Frontend readiness:

- [ ] `npm run lint`, `npm run typecheck` and `npm run build` pass.
- [ ] Playwright E2E passes.
- [ ] Visual smoke screenshots pass.
- [ ] `NEXT_PUBLIC_API_BASE_URL` points to the beta/staging API URL.

AI/LLM readiness:

- [ ] LLM Gateway routes are documented.
- [ ] Fallback model/provider behavior is verified.
- [ ] Timeout and retry settings are reviewed.
- [ ] LLM usage metering is enabled.
- [ ] Token/call quotas are configured for beta.
- [ ] Estimated cost budget is written down.

Security readiness:

- [ ] `JWT_SECRET_KEY` or equivalent token secret is non-default and supplied outside git.
- [ ] `AUTH_DEV_CODE_ENABLED=false` for beta.
- [ ] `AUTH_DEV_CODE` is not the default `000000`.
- [ ] DB and Redis ports are not exposed to the public internet.
- [ ] `/metrics` is not publicly reachable without deployment-level protection.
- [ ] RBAC roles for `admin` and `content_operator` are confirmed.
- [ ] No secrets are committed.

Privacy readiness:

- [ ] `GET /api/me/data-summary` is verified.
- [ ] `GET /api/me/data-export` is verified for redaction.
- [ ] `POST /api/me/data-deletion-request` and `POST /api/me/data-delete-confirm` are verified.
- [ ] Data deletion confirmation phrase `DELETE_MY_DATA` is verified with a test user.
- [ ] Users are informed that backups can retain deleted data until the backup retention window expires.
- [ ] Support notes must not contain raw answers, prompts, completions, tokens, secrets, verification codes or full phone numbers.

Observability readiness:

- [ ] Structured logs include `request_id`.
- [ ] `/metrics` can be scraped from a trusted network path.
- [ ] Alert rule file check passes.
- [ ] Incident owner is assigned.
- [ ] Daily operational check owner is assigned.

Backup readiness:

- [ ] Staging backup drill has run at least once.
- [ ] Backup file size and SHA256 are recorded.
- [ ] Restore drill result is recorded.
- [ ] Migration pre-backup rule is understood.
- [ ] Backup artifacts are not committed.

Release readiness:

- [ ] Release candidate commit SHA is recorded.
- [ ] Immutable image tag or build identifier is recorded.
- [ ] Release evidence is filled in.
- [ ] Staging smoke test passes.
- [ ] Active P0/P1 incidents are checked before beta start.

Incident readiness:

- [ ] Incident owner and escalation contact are known.
- [ ] P0/P1/P2/P3 severity rules are understood.
- [ ] Incident evidence template is ready.
- [ ] Rollback path is reviewed.
- [ ] Database restore requires separate approval.

Cost readiness:

- [ ] LLM estimated daily budget is defined.
- [ ] Usage summary API is available.
- [ ] LLM cost spike alert rule is reviewed.
- [ ] Quota values are written down in beta evidence.

## Mandatory Completion Items

Before inviting users:

- [ ] Run `scripts/beta-readiness-check.ps1`.
- [ ] Run `scripts/staging-smoke.ps1` against the target beta/staging endpoint.
- [ ] Confirm `/health`, `/ready` and `/metrics`.
- [ ] Run `scripts/check-alert-rules.ps1`.
- [ ] Create and verify a PostgreSQL backup.
- [ ] Record backup evidence.
- [ ] Verify privacy export and deletion APIs with a test user.
- [ ] Confirm LLM Gateway primary/fallback route.
- [ ] Confirm Redis-backed rate limit and cache backend for staging/beta.
- [ ] Confirm quotas and rate limits are enabled.
- [ ] Confirm default auth code and default JWT secret are not used.
- [ ] Confirm API keys and database passwords are configured outside git.
- [ ] Confirm frontend API base URL.
- [ ] Confirm admin and content-operator roles.
- [ ] Confirm test-user data cleanup plan.
- [ ] Confirm incident owner.

## Beta Forbidden Items

Do not start beta if any of these are true:

- Default JWT or token secret is used.
- Default verification code `000000` is accepted in beta.
- Database or Redis ports are exposed publicly.
- `/metrics` is public internet accessible without access control.
- Migration is planned without a verified backup.
- Rate limit or LLM quota is disabled.
- Backend RBAC is bypassed.
- Real secrets are committed to git.
- Staging is treated as permanent production without evidence and retention policy.
- Prompt text, completion text, raw answer text or full phone numbers are pasted into issues, incidents, release notes or support notes.
- Production is deployed automatically from this repository.

## Beta Operation SOP

User invitation:

1. Select 5 to 10 invited users.
2. Explain the beta limitations and lack of SLA.
3. Provide the beta URL and support contact.
4. Do not invite enterprise customers or paid users.

Test account preparation:

1. Create one operator-owned test user.
2. Run login and full training loop.
3. Verify report, wrong-book, history, ability and privacy endpoints.
4. Delete or clean the test-user training data before inviting users if the environment should start clean.

Pre-deployment check:

1. Confirm release candidate commit SHA and image tags.
2. Confirm environment variables from `.env.staging.example` are set outside git.
3. Confirm database backup and restore evidence.
4. Confirm alert rules and incident owner.
5. Confirm LLM cost budget and quota.

Post-deployment smoke:

1. Run `/health`.
2. Run `/ready`.
3. Run `/metrics` from a trusted path.
4. Run `scripts/staging-smoke.ps1`.
5. Run one login and one training session with the test user.
6. Record request ids in beta evidence.

Daily check:

1. Check active P0/P1 incidents.
2. Check `/ready`.
3. Check API 5xx, p95 latency, rate-limit/quota spikes and LLM failure/cost metrics.
4. Check async job failures.
5. Review user feedback and support notes.
6. Confirm no sensitive data was pasted into tickets or chat.

Issue feedback:

1. Record user-visible symptom, time and request id.
2. Do not ask for raw answers, prompts, tokens or full phone numbers.
3. Link to incident evidence if severity is P0/P1.
4. Track follow-up tasks after the beta window.

Privacy request handling:

1. Ask the user to use current-user export/delete APIs when possible.
2. For operator-assisted deletion, verify identity through existing auth context.
3. Record audit evidence and backup retention note.
4. Do not manually edit backups during normal beta operations.

End-of-beta cleanup:

1. Export aggregate findings without sensitive data.
2. Clear test-user training data if needed.
3. Preserve audit, release and incident evidence.
4. Archive beta evidence.
5. Decide whether to continue, pause, or move to production-readiness work.

## Beta Exit Criteria

Beta can be considered successful when:

- No P0/P1 incidents for 3 consecutive beta days.
- Core flow success rate is acceptable for invited-user volume.
- API p95 latency is acceptable for the trial.
- LLM failure rate is acceptable or fallback behavior is adequate.
- Token/cost usage stays inside the beta budget.
- User feedback is logged and triaged.
- Data export and deletion flow has been verified during the beta window.
- Backup/restore evidence exists for the beta environment.
- Known risks have assigned follow-up tasks.

## Go / No-Go Checklist

| Item | Owner | Status | Evidence | Notes |
| --- | --- | --- | --- | --- |
| Release candidate commit recorded |  |  |  |  |
| Staging/beta smoke passed |  |  |  |  |
| `/health` and `/ready` passed |  |  |  |  |
| `/metrics` trusted scrape verified |  |  |  |  |
| Alert rules checked |  |  |  |  |
| Backup created and verified |  |  |  |  |
| Restore drill reviewed |  |  |  |  |
| Migration plan reviewed |  |  |  |  |
| JWT secret non-default |  |  |  |  |
| Dev auth disabled |  |  |  |  |
| DB/Redis not public |  |  |  |  |
| Rate limits and quotas enabled |  |  |  |  |
| Redis backend enabled for beta |  |  |  |  |
| LLM Gateway route/fallback confirmed |  |  |  |  |
| LLM cost budget confirmed |  |  |  |  |
| Admin/content_operator roles confirmed |  |  |  |  |
| Privacy export/delete verified |  |  |  |  |
| Incident owner assigned |  |  |  |  |
| User invitation list approved |  |  |  |  |
| Known risks accepted |  |  |  |  |

Decision:

```text
GO / NO-GO:
Decision owner:
Decision time:
Required follow-ups:
```
