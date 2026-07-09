# Incident Evidence Template

Use this template for P0/P1 incidents and for any P2 incident that involves data risk, cost risk or release rollback.

## Identity

- Incident ID:
- Severity:
- Status:
- Started at:
- Detected by:
- Incident owner:
- Communications owner:

## Impact

- Affected services:
- Affected routes:
- Affected users estimate:
- User-visible symptoms:
- Business impact:

## Evidence

- Alert names:
- Key metrics:
- Time window:
- Request IDs:
- Latest release:
- Commit SHA:
- Image tags:
- Recent config changes:
- Recent migration:
- Backup evidence:

## Triage

- `/health` result:
- `/ready` result:
- Database status:
- Redis status:
- LLM provider status:
- Worker status:
- Suspected cause:

## Actions

- Actions taken:
- Rollback decision:
- Code rollback used:
- Config rollback used:
- Backup or restore used:
- Restore approval:
- Smoke test result:

## Resolution

- Resolved at:
- Root cause:
- Customer or user communication:
- Follow-up tasks:
- Owner:
- Due date:

## Sensitive Data Check

- [ ] No tokens or secrets included.
- [ ] No verification codes included.
- [ ] No full phone numbers included.
- [ ] No prompt text included.
- [ ] No completion text included.
- [ ] No user answer text included.
