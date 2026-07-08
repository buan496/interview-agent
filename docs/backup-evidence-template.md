# Backup Evidence Template

Use this template whenever a local or staging database backup is created for a release candidate, migration rehearsal, restore drill, or operational recovery exercise.

## Backup Identity

- Environment:
- Reason:
- Related release:
- Commit SHA:
- Operator:
- Backup time UTC:

## Database

- Compose file:
- Env file:
- PostgreSQL service:
- Database name:
- Database user:

## Backup Artifact

- Backup file name:
- Backup storage location:
- File size bytes:
- SHA256:
- Verification command:
- Verification result:

## Restore Drill

- Restore drill required: yes / no
- Restore target:
- Restore command:
- Restore result:
- Smoke test result:
- Observed request_id:

## Production Handling

- Production data involved: yes / no
- Encrypted storage confirmed: yes / no
- Access limited to approved operators: yes / no
- Retention expiry:
- Deletion confirmed after expiry: yes / no

## Notes

- Known risks:
- Follow-up actions:
