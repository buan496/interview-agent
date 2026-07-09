# Incident Runbook

This runbook defines the first operational response flow for Interview Agent. It assumes operators have access to trusted `/health`, `/ready`, `/metrics`, structured logs, release evidence and database tooling. It does not require an external alerting service.

## First Five Minutes

1. Identify severity: P0, P1, P2 or P3 from `docs/alerting.md`.
2. Create an incident record using `docs/incident-evidence-template.md` for P0/P1.
3. Freeze releases if the incident may be caused by a release or migration.
4. Capture the alert name, start time, affected service and key metric values.
5. Check `/health`, `/ready` and recent release evidence.
6. Never copy secrets, tokens, verification codes, full phone numbers, prompts, completions or user answer text into the incident record.

## API 5xx Error Rate Spike

Triage:

- Check `/ready` for database and Redis readiness.
- Search structured logs for `http_request_exception`.
- Use `request_id` from user reports or 500 responses.
- Check the latest release, migration status and config changes.
- Check LLM gateway fallback logs if the failing route involves scoring.

Recovery:

- Roll back the API image if the regression started after a release.
- Restore the previous safe config if a config change caused failures.
- Stop or pause workers if they are amplifying database or provider failures.
- Do not restore a database unless code rollback and config rollback are insufficient and backup evidence has been reviewed.

## Database Not Ready

Triage:

- Run `docker compose ps postgres` for local or staging.
- Inspect database container logs.
- Verify `DATABASE_URL` is configured for the target environment.
- Check Alembic migration status and latest migration evidence.
- Confirm whether a migration is currently running.

Recovery:

- Restart PostgreSQL only after confirming volume health.
- Stop application rollout if migrations failed.
- Restore from backup only with explicit approval, verified SHA256 and restore plan.
- After recovery, run `/ready`, staging smoke and relevant backend tests.

## Redis Not Ready

Triage:

- Run `docker compose ps redis`.
- Inspect Redis container logs.
- Verify `REDIS_URL`, `RATE_LIMIT_BACKEND`, `CACHE_BACKEND` and `ASYNC_JOB_BACKEND`.
- Check whether production is correctly failing closed instead of silently falling back to memory.

Recovery:

- Restart Redis.
- Restart API and worker if they cache failed Redis connections.
- Do not disable production safety rate limits just to clear the alert.
- For non-critical cache issues, reduce cache usage first; for rate limits and async jobs, preserve safety boundaries.

## LLM Failure Spike

Triage:

- Check provider API key configuration without printing the key.
- Check provider status and network connectivity.
- Inspect `llm_gateway.call` logs by `request_id`.
- Compare `interview_agent_llm_calls_total{status="failed"}` with `llm_usage_records`.
- Check whether fallback attempts are succeeding.

Recovery:

- Switch model route to a configured fallback provider/model.
- Increase timeout only if provider latency is the confirmed cause and user impact is acceptable.
- Temporarily reduce high-cost or high-volume features.
- In staging only, downgrade to mock/local rule behavior for validation.

## Token Or Cost Spike

Triage:

- Inspect `interview_agent_llm_estimated_cost_total` and `interview_agent_llm_tokens_total` by feature/model.
- Check `/api/me/usage/summary` only for authorized user-specific investigation.
- Check quota metrics and quota settings.
- Check recent feature routing changes and async jobs.

Recovery:

- Lower LLM token or call quotas.
- Route affected features to lower-cost models.
- Pause high-cost async jobs if they are the spike source.
- Preserve evidence that cost is estimated, not a billing statement.

## Async Job Failure Spike

Triage:

- Check worker logs for `async_job.failed`.
- Inspect `async_jobs.status`, `attempts`, `error_type` and `updated_at`.
- Check Redis readiness and queue backend config.
- Identify affected `job_type`.

Recovery:

- Restart worker.
- Pause new enqueue paths if failures continue.
- Re-run failed jobs only after fixing the root cause.
- Lower worker concurrency or job volume if database/provider pressure is involved.

## Release Regression

Triage:

- Open release evidence for the latest release candidate.
- Compare metrics before and after deployment.
- Check smoke test result and observed request id.
- Check migration result and backup evidence.
- Identify whether the failure is code, config, dependency or migration related.

Recovery:

- Prefer code rollback when schema compatibility allows it.
- Use config rollback for unsafe runtime settings.
- Treat database restore as a separate approval path with backup evidence.
- Fill follow-up tasks before closing the incident.

## Closing An Incident

Close only after:

- service health and readiness are normal
- user-visible symptoms stopped
- key metrics returned to acceptable range
- rollback or fix is recorded
- backup/restore evidence is attached when used
- follow-up tasks are created for prevention

## Public Beta Incident Handling

During an invited beta:

- Treat any data safety, privacy deletion/export failure, auth bypass, public secret exposure, or database/Redis exposure as P0 until triaged.
- Pause new user invitations while a P0/P1 incident is active.
- Record the beta id, release commit, request ids, affected flow and current Go / No-Go status in incident evidence.
- Review `docs/public-beta-evidence-template.md` before rollback or data restore decisions.
- If user data deletion or export is involved, follow `docs/privacy-and-data-lifecycle.md` and record the backup-retention boundary.
- Do not paste raw answers, prompts, completions, tokens, secrets, verification codes or full phone numbers into incident notes.

After a beta P0/P1, resume invitations only after the incident owner updates the beta evidence and explicitly records a new Go decision.
