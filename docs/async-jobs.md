# Async Job Queue Foundation

PR #50 adds the first asynchronous job queue foundation for Interview Agent. The goal is to move long-running, retryable and batch-style AI tasks out of synchronous request paths without introducing Celery, a workflow engine, WebSocket delivery or a frontend job center.

## Why Async Jobs

Some backend operations are safe but potentially slow:

- Agent Memory refresh.
- Future report generation.
- Future question import.
- Future rubric validation.

The v1 queue keeps the API responsive, gives operators a durable job ledger and provides a worker entrypoint that can be scaled separately from the API process.

## Supported Job Types

Current v1 supported job type:

- `memory_refresh`: refreshes the current user's Agent Memory from existing reports, wrong-book records and tag statistics.

Reserved future job types:

- `report_generation`
- `question_import`
- `rubric_validation`

## Data Model

`async_jobs` stores:

- `id`
- `job_type`
- `user_id`
- `status`: `queued`, `running`, `succeeded`, `failed`, `canceled`
- `payload_json`
- `result_json`
- `error_type`
- `error_message`
- `attempts`
- `max_attempts`
- `idempotency_key`
- `created_at`
- `started_at`
- `finished_at`
- `updated_at`

Indexes cover:

- `user_id + created_at`
- `status + created_at`
- `job_type + status`
- `idempotency_key`

Payload and result data must stay small and non-sensitive. The memory refresh payload stores only safe metadata such as `user_id` and `trigger`.

## Queue Backend

Config:

```text
ASYNC_JOBS_ENABLED=true
ASYNC_JOB_BACKEND=memory
ASYNC_JOB_QUEUE_NAME=interview-agent:async-jobs
ASYNC_JOB_MAX_ATTEMPTS=3
ASYNC_JOB_WORKER_POLL_SECONDS=2
```

Backends:

- `memory`: process-local queue for local development and tests.
- `redis`: Redis list backend using job ids as messages.

Production should use Redis. Production config validation rejects `ASYNC_JOB_BACKEND=memory` when async jobs are enabled.

## Worker

Run the worker with:

```powershell
python -m app.worker
```

The worker:

- Dequeues a job id.
- Marks the job `running`.
- Dispatches by `job_type`.
- Updates `succeeded` or `failed`.
- Re-enqueues failed jobs when attempts remain.
- Emits logs, audit events and metrics.

Docker Compose includes a `worker` service using the same backend image as the API.

## Memory Refresh Async Flow

API:

```text
POST /api/me/memories/refresh-async
GET  /api/me/jobs/{job_id}
GET  /api/me/jobs
```

Flow:

1. The current user calls `POST /api/me/memories/refresh-async`.
2. The API creates an `async_jobs` row scoped by `current_user.id`.
3. The API enqueues the job id and returns `job_id` with `status=queued`.
4. The worker runs `refresh_user_memories`.
5. The job result records `created`, `updated` and `total_active`.

The existing synchronous API remains available:

```text
POST /api/me/memories/refresh
```

## Failure and Retry

- `attempts` increments when a worker marks a job `running`.
- If a job fails and `attempts < max_attempts`, the job returns to `queued` and is re-enqueued.
- If attempts reach `max_attempts`, the job becomes `failed`.
- Worker failures do not break the API request that created the job.
- `error_message` is sanitized and truncated.

## Idempotency

`idempotency_key` is available for future callers that need duplicate suppression. V1 checks for an existing job with the same `user_id`, `job_type` and `idempotency_key` before inserting a new row. The memory refresh async endpoint does not require a client-provided key yet.

## Metrics, Audit and Logs

Metrics:

- `interview_agent_async_jobs_created_total{job_type}`
- `interview_agent_async_jobs_completed_total{job_type,status}`
- `interview_agent_async_job_duration_seconds{job_type}`
- `interview_agent_async_jobs_in_progress{job_type}`

Audit events:

- `async_job_created`
- `async_job_succeeded`
- `async_job_failed`
- `async_job_retry_scheduled`

Structured logs include `job_id`, `job_type`, status and attempts. Metrics labels intentionally exclude `job_id`, `user_id`, `request_id`, phone numbers and sensitive text.

## Sensitive Data Rules

Async jobs must not store:

- Raw user answer text.
- Prompt text.
- Model completion text.
- Bearer tokens.
- API keys or secrets.
- Verification codes.
- Full phone numbers.

Payload sanitization redacts sensitive key names such as `answer_text`, `prompt`, `completion`, `token`, `secret` and `verification_code`.

## Privacy and Data Lifecycle

PR #52 treats `async_jobs` as current-user operational data:

- `/api/me/data-export` includes only job type, status, attempts, timestamps and sanitized payload/result summaries.
- `/api/me/data-delete-confirm` deletes the current user's async job rows as part of the `training_data` deletion scope.
- Worker audit events remain in `audit_events` as sanitized operational records.
- Existing PostgreSQL backups can retain historical job rows until the backup retention window expires.

Job payloads and results must stay small and safe. They must not contain raw answers, prompts, completions, tokens, secrets, verification codes or full phone numbers.

## Staging Notes

Staging uses:

```text
ASYNC_JOB_BACKEND=redis
ASYNC_JOB_QUEUE_NAME=interview-agent:staging:async-jobs
```

Run both `api` and `worker` services. Redis readiness is included in `/ready` when the async job backend is Redis.

## Future Work

Out of scope for v1:

- Celery.
- Workflow engine.
- Distributed locks.
- Delayed jobs.
- WebSocket status push.
- Frontend job center.
- Tenant-specific job policies.

Future PRs can add report async generation, batch question import, rubric validation jobs, worker concurrency limits, dead-letter handling and an admin/operator job dashboard.
