# Public Beta Evidence Template

Use this template before starting, extending or closing a small invited beta. Keep the completed evidence outside user-facing docs if it contains internal URLs, operator names or environment details.

Do not paste secrets, tokens, verification codes, full phone numbers, prompt text, completion text or raw user answer text into this file.

## Beta Metadata

- beta_id:
- target_users_count:
- environment:
- commit_sha:
- image_tag:
- domain/base_url:
- api_base_url:
- operator:
- incident_owner:
- start_time:
- planned_end_time:
- actual_end_time:

## Environment Evidence

- `.env.staging.example` reviewed:
- runtime secrets configured outside git:
- `APP_ENV`:
- `AUTH_DEV_CODE_ENABLED=false` confirmed:
- default `AUTH_DEV_CODE=000000` rejected:
- non-default JWT/token secret confirmed:
- `DATABASE_URL` configured:
- `REDIS_URL` configured:
- `RATE_LIMIT_BACKEND=redis` confirmed:
- `CACHE_BACKEND=redis` confirmed:
- `NEXT_PUBLIC_API_BASE_URL` confirmed:
- DB public exposure checked:
- Redis public exposure checked:
- `/metrics` exposure restricted:

## Release Evidence

- release PR:
- release workflow run:
- release evidence link:
- staging deployment drill evidence link:
- staging deployment drill result:
- migration status:
- migration revision:
- docker image tag:
- rollback plan:
- known release risks:

## Smoke Test Evidence

- beta readiness check result:
- staging deployment drill static check result:
- staging smoke test result:
- `/health` result:
- `/ready` result:
- `/metrics` trusted scrape result:
- observed request_id:
- frontend login page result:
- core training flow result:
- admin access check:

## Backup Evidence

- backup evidence link:
- backup file name:
- backup size:
- backup SHA256:
- restore drill result:
- migration pre-backup confirmed:
- backup retention window:

## Alert and Incident Evidence

- alert rules check result:
- active P0/P1 incidents checked:
- incident runbook reviewed:
- incident evidence template ready:
- rollback owner:
- database restore approver:

## Privacy Evidence

- data summary API verified:
- data export API verified:
- export redaction verified:
- data deletion request verified:
- data delete confirmation verified:
- backup residue note accepted:
- support sensitive-data rule reviewed:

## LLM and Cost Evidence

- LLM Gateway primary route:
- LLM Gateway fallback route:
- mock evaluation harness result:
- model comparison result:
- timeout/retry settings:
- usage metering enabled:
- daily token quota:
- monthly token quota:
- daily call quota:
- estimated beta budget:
- cost review owner:

## User Plan

- invited users:
- onboarding note reviewed:
- support contact:
- feedback collection path:
- test account prepared:
- test data cleanup plan:

## Go / No-Go Decision

- decision: GO / NO-GO
- decision owner:
- decision time:
- accepted risks:
- blocking issues:
- follow_up_tasks:

## Beta Closeout

- closeout date:
- user feedback summary:
- incidents:
- privacy requests:
- cost summary:
- data cleanup result:
- next decision:
