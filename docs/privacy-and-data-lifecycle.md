# Privacy and Data Lifecycle v1

PR #52 adds the first privacy and data lifecycle foundation for Interview Agent. It gives the current authenticated user a way to inspect, export and delete their own training data while keeping security audit records, backups and operational ledgers clearly bounded.

This is a product and engineering baseline, not a complete GDPR, DSR or enterprise compliance system. It does not add a frontend privacy center, a ticket workflow, automatic retention jobs, account deletion, or production data operations.

## Data Classification

Current-user product data:

- `users`: account profile fields. Exports use masked phone numbers only.
- `sessions`: training sessions and report JSON summaries.
- `session_questions`: question attempt metadata. Raw answer text is redacted from exports.
- `evaluation_results`: scores, rubric references and structured feedback summaries. Raw model output is excluded.
- `wrong_book`: user-scoped wrong-book records.
- `user_tag_stats`: tag-level training aggregates.
- `practice_plans`: current-user recommendation plans.
- `agent_memories`: long-term user training signals.
- `async_jobs`: current-user job status and sanitized payload/result summaries.
- `llm_usage_records`: usage and estimated-cost metadata.

Security and operational data:

- `audit_events`: security/admin/privacy event ledger. It is retained for safety and incident reconstruction.
- Structured logs and Prometheus metrics: aggregate or request-level operational telemetry, not user export payloads.
- PostgreSQL backups: operational recovery artifacts with separate retention and approval rules.

Shared content data:

- Question bank, rubric definitions, companies, positions and tags are product/content data. They are not part of an individual user's export or deletion scope.

## User Data Summary

API:

```text
GET /api/me/data-summary
```

The response is scoped by `current_user.id` and returns counts for:

- sessions
- session_questions
- messages
- evaluation_results
- reports
- wrong_book
- user_tag_stats
- practice_plans
- agent_memories
- async_jobs
- llm_usage_records

No cross-user selector is accepted.

## User Data Export

API:

```text
GET /api/me/data-export
```

The response is JSON and uses `export_version=privacy-export-v1`. V1 does not generate downloadable files or write export artifacts to disk.

Exported sections:

- masked user profile
- summary counts
- session summaries
- session question attempt summaries
- evaluation summaries
- report summaries
- wrong-book records
- tag statistics
- practice plans
- Agent Memory records
- async job summaries
- LLM usage summaries

The export writes an audit event:

- `user_data_exported`

The audit metadata stores record counts only, not the export body.

## Data Excluded From Export

Exports must not include:

- bearer tokens
- JWT secrets or token secrets
- API keys
- verification codes
- passwords or password-like values
- full phone numbers
- prompt text
- model completion text
- raw user answer text
- `Message.content`
- `SessionQuestion.answer_text`
- `EvaluationResult.raw_model_output`
- Authorization headers
- database URLs or other infrastructure secrets

The backend uses `sanitize_export_payload` to recursively redact sensitive key names in nested payloads. Token counts such as `prompt_tokens` and `completion_tokens` are allowed because they are usage metadata, not prompt or completion bodies.

## Data Deletion Flow

APIs:

```text
POST /api/me/data-deletion-request
POST /api/me/data-delete-confirm
```

`data-deletion-request` returns:

- deletion scope: `training_data`
- impact counts
- confirmation phrase: `DELETE_MY_DATA`
- warning text

`data-delete-confirm` requires:

```json
{"confirmation_phrase":"DELETE_MY_DATA"}
```

If the phrase is wrong, the request is rejected and audited with:

- `user_data_delete_denied`

If the phrase is correct, the backend deletes only the current user's training data and audits:

- `user_data_deleted`

## V1 Deletion Scope

Deleted for the current user:

- `messages` linked to the user's session questions
- `evaluation_results`
- `session_questions`
- `sessions`
- `wrong_book`
- `user_tag_stats`
- `practice_plans`
- `agent_memories`
- `async_jobs`
- `llm_usage_records`

Retained:

- the `users` account row
- `audit_events`
- shared question bank content
- rubric definitions and versions
- companies, positions and tags
- existing database backups until their retention window expires

V1 uses hard deletion for current-user training data to keep user-facing APIs clean after deletion. It retains the account and security audit ledger. A future account-closure PR can add account-level `deleted_at`, login blocking and stronger anonymization once product requirements are defined.

## Audit and Metrics

Audit actions:

- `user_data_exported`
- `user_data_deletion_requested`
- `user_data_delete_denied`
- `user_data_deleted`

Audit metadata is limited to record counts, deletion scope and denial reason. It does not store export content, raw answers, prompts, completions, tokens, secrets, verification codes or full phone numbers.

Prometheus counters:

- `interview_agent_data_exports_total{status}`
- `interview_agent_data_deletions_total{status,scope}`

Labels stay low-cardinality. They do not include user id, request id, phone numbers, session ids or resource ids.

## Backups and Retention Boundary

Deleting training data from the live database does not instantly remove historical data from existing PostgreSQL backups. Production backup policy must define:

- encrypted backup storage
- retention windows
- access controls
- restore approval
- deletion evidence after retention expiry

If a backup is restored, operators must understand that restored data reflects the backup timestamp. Any production restore involving a user deletion request needs explicit approval and privacy review.

## Agent Memory Lifecycle

Agent Memory is user-scoped training data in v1:

- included in current-user export
- deleted by current-user training-data deletion
- never stores raw answers, prompts or completions
- retained in audit only as sanitized memory operation events

Vector memory, RAG memory and tenant-level memory governance remain future work.

## Async Job Lifecycle

Async job rows are user-scoped operational records:

- export includes only status, type, attempts and sanitized payload/result summaries
- deletion removes current-user job rows
- job payloads must not contain raw answers, prompts, completions, tokens, secrets, verification codes or full phone numbers

## Admin Access Boundary

Admins and content operators do not get a generic user-data export or delete endpoint in v1. Privacy APIs are current-user APIs only. Admin access to audit records remains governed by RBAC and audit log rules.

## Beta Checklist

Before a small real-user trial:

- [ ] Confirm production auth does not use the default development verification code.
- [ ] Confirm `/api/me/data-export` omits raw answers, prompts, completions and full phone numbers.
- [ ] Confirm `/api/me/data-delete-confirm` deletes only current-user training data.
- [ ] Confirm `audit_events` records export, deletion request, deletion denial and deletion success.
- [ ] Confirm metrics expose aggregate export/deletion counters without user labels.
- [ ] Confirm backup retention and restore approval are documented for the trial environment.
- [ ] Confirm support scripts and incident notes do not paste sensitive data.

Use [Public Beta Readiness Checklist](public-beta-readiness.md) and [Public Beta Evidence Template](public-beta-evidence-template.md) before inviting real users. The beta evidence should record data export, deletion, backup residue and support-note handling results.

## Future Work

- Account closure with `users.deleted_at` and login blocking.
- Automated retention jobs for stale async jobs, usage summaries and inactive memories.
- Stronger anonymization for cost ledgers if business reporting needs long retention.
- Encrypted export generation and expiring download links.
- Enterprise DSR workflow with approval, evidence and operator assignment.
- Tenant-aware privacy controls after organization modeling exists.
