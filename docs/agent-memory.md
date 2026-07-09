# Agent Memory v1

PR #48 adds the backend foundation for Agent Memory. The goal is to persist long-term, user-scoped training signals that can improve future recommendations without adding a vector database, RAG memory, Multi-Agent orchestration or LLM-based memory extraction.

## Goals

- Record durable user training signals such as weaknesses, strengths, recurring issues and next-practice recommendations.
- Keep every memory strictly scoped by `user_id`.
- Let the current user list, refresh and archive their own memories.
- Refresh memories from existing training data after report generation.
- Keep memory refresh best-effort so answer submission and report generation are not failed by memory errors.

## Data Sources

Memory v1 uses deterministic rules over existing product data:

- `Session.report` question summaries and scores.
- `EvaluationResult` and report rubric references.
- `WrongBook` fail counts and latest scores.
- `UserTagStat` average score and attempt counts.
- `PracticePlan` only as a lightweight consumer of active weakness memories.

It does not call an LLM to extract memories.

## Data Model

`agent_memories` fields:

- `id`
- `user_id`
- `memory_type`: `weakness`, `strength`, `preference`, `training_goal`, `recurring_issue`, `recommendation`
- `title`
- `summary`
- `tags_json`
- `evidence_json`
- `confidence`
- `status`: `active` or `archived`
- `source_type`: `report`, `wrong_book`, `ability_profile`, `practice_plan` or `system_rule`
- `source_id`
- `first_seen_at`
- `last_seen_at`
- `created_at`
- `updated_at`

Indexes cover `user_id + status`, `user_id + memory_type`, and `user_id + last_seen_at`.

## Sensitive Data Rules

Memory records must not store:

- Raw user answer text.
- Prompt text.
- Model completion text.
- Bearer tokens.
- API keys or secrets.
- Verification codes.
- Full phone numbers.

`evidence_json` stores only references and small numeric summaries such as `report_id`, `session_id`, `question_id`, `tag_id`, `tag`, `score`, `avg_score`, `attempts`, `fail_count` and `rubric_version_id`.

## Generation Rules

Memory v1 is rule-based:

- Report question score `< 70` creates or updates a `weakness` memory for each related tag.
- Report question score `>= 85` creates or updates a `strength` memory.
- Report question score `< 80` creates or updates a `recommendation` memory.
- `UserTagStat.attempts >= 2` with average score `< 70` creates or updates a `weakness`.
- `UserTagStat.attempts >= 2` with average score `>= 85` creates or updates a `strength`.
- `WrongBook.fail_count >= 2` creates or updates a `recurring_issue`.

If the same user already has an active memory with the same `memory_type` and primary tag, the service updates the existing memory instead of creating unlimited duplicates. Confidence starts at `0.50`, increases by `0.10` per repeat, and is capped at `0.95`.

## API

Current-user APIs:

```text
GET  /api/me/memories
POST /api/me/memories/{memory_id}/archive
POST /api/me/memories/refresh
POST /api/me/memories/refresh-async
```

`GET /api/me/memories` supports:

- `memory_type`
- `status`
- `tag`
- `limit`
- `offset`

All APIs use `get_current_user` and query with `current_user.id`. A user archiving another user's memory receives `404`.

`POST /api/me/memories/refresh-async` creates a user-scoped `memory_refresh` job in `async_jobs` and returns `job_id` with `status=queued`. Job status can be queried through `GET /api/me/jobs/{job_id}` or `GET /api/me/jobs`. The async payload stores only safe metadata such as `user_id` and `trigger`; it does not store raw answers, prompts or completions.

## PracticePlan Integration

`PracticePlan` now reads active `weakness` and `recurring_issue` memories for the current user and gives those tags priority in weak-tag recommendations. Archived memories are ignored. This is a lightweight ranking signal only; the existing training plan logic remains intact.

## Audit and Metrics

Audit events:

- `memory_created`
- `memory_updated`
- `memory_archived`

Audit metadata stores only safe summaries such as memory type, status, source type and tag count.

Metrics:

- `interview_agent_memories_created_total{memory_type}`
- `interview_agent_memory_refresh_total{status,trigger}`

Metric labels intentionally exclude `user_id`, `memory_id`, `session_id`, `request_id`, phone numbers, answer text, prompt text, completion text, tokens and secrets.

## Failure Handling

Report generation commits before memory refresh. If memory refresh fails, the answer/report flow remains successful, the refresh failure is logged through observability, and a failed refresh metric is incremented.

The async memory refresh worker has its own retry path. A worker failure marks the job failed or re-queues it when attempts remain; it does not affect the synchronous answer/report flow or the existing sync refresh API.

## Privacy and Data Lifecycle

PR #52 treats Agent Memory as current-user training data:

- Memory records are included in `/api/me/data-export` with only stored titles, summaries, tags, evidence summaries, confidence and source metadata.
- Memory records are deleted by `/api/me/data-delete-confirm` when the user confirms the `training_data` deletion scope.
- Memory audit events remain in `audit_events` as sanitized security records.
- Existing PostgreSQL backups can retain memory rows until the backup retention window expires.

Memory exports and deletion audit metadata must not include raw answer text, prompt text, model completion text, tokens, secrets, verification codes or full phone numbers.

## Future Work

Out of scope for v1:

- Vector database memory.
- RAG memory retrieval.
- Multi-Agent memory workflows.
- LLM-based memory extraction or summarization.
- Admin global memory browsing.
- Tenant-scoped memory governance.

Future PRs can add controlled LLM extraction, vector retrieval, memory evaluation, automated retention policies and tenant-aware admin tooling after the privacy and governance boundaries are designed.
