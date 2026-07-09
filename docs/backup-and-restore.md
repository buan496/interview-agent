# Backup and Restore Foundation

This document defines the PostgreSQL backup and restore baseline for Interview Agent. It is intended for local and staging environments first. Production backup and restore require separate human approval, encrypted storage, and operational evidence.

## Goals

- Create repeatable PostgreSQL backups before migrations and release rehearsals.
- Verify backup artifacts with file size and SHA256 checksum.
- Provide a controlled restore path for local and staging recovery drills.
- Make backup evidence part of the release process.
- Avoid committing database dumps, secrets, tokens, prompts, user answers, or production data.

## PostgreSQL Backup Scope

PostgreSQL stores durable product data, including users, sessions, reports, wrong-book records, question bank content, rubrics, audit logs, usage records, and migrations. It is the primary backup target.

The backup script uses `pg_dump` inside the Compose `postgres` service and copies a plain SQL dump to the local `backups/` directory.

## Redis Backup Scope

Redis currently supports rate limit counters and cache foundation behavior. It is not the source of truth for user training data.

Current policy:

- Local/test Redis does not require backup.
- Staging Redis can be restarted or rebuilt if counters/cache are lost.
- Production Redis persistence may be useful for operational continuity, but PostgreSQL remains the required durable backup target.
- Do not treat Redis AOF/RDB as a replacement for PostgreSQL backup.

## Backup Commands

Local backup:

```powershell
.\scripts\backup-postgres.ps1 -Environment local
```

Staging backup:

```powershell
.\scripts\backup-postgres.ps1 `
  -Environment staging `
  -EnvFile .env.staging `
  -OutputDir backups
```

Custom Compose files:

```powershell
.\scripts\backup-postgres.ps1 `
  -Environment staging `
  -ComposeFile docker-compose.staging.yml `
  -EnvFile .env.staging `
  -ServiceName postgres `
  -DatabaseName interview_agent_staging `
  -DatabaseUser interview
```

Output naming:

```text
interview-agent-{environment}-{yyyyMMddTHHmmssZ}.sql
```

The script prints the final path, file size, SHA256 checksum, and UTC timestamp. It does not print database passwords.

## Verify Backup

Basic verification:

```powershell
.\scripts\verify-postgres-backup.ps1 -BackupFile .\backups\interview-agent-staging-20260708T120000Z.sql
```

Optional structure marker verification:

```powershell
.\scripts\verify-postgres-backup.ps1 `
  -BackupFile .\backups\interview-agent-staging-20260708T120000Z.sql `
  -ExpectedTables users,sessions,questions
```

Verification records:

- file exists
- file size is non-zero
- SHA256 checksum
- optional table markers

It does not parse sensitive row contents.

## Restore Commands

Local restore:

```powershell
.\scripts\restore-postgres.ps1 `
  -Environment local `
  -BackupFile .\backups\interview-agent-local-20260708T120000Z.sql
```

Staging restore:

```powershell
.\scripts\restore-postgres.ps1 `
  -Environment staging `
  -EnvFile .env.staging `
  -BackupFile .\backups\interview-agent-staging-20260708T120000Z.sql
```

By default, restore requires typing `RESTORE`. The restore script is limited to `local` and `staging` to avoid accidental production operations.

## Restore Drill

Recommended staging drill:

1. Create a staging backup.
2. Record path, size, checksum, operator, and reason in `docs/backup-evidence-template.md`.
3. Restore the backup into a staging or disposable local database.
4. Run `/health`, `/ready`, and `scripts/staging-smoke.ps1`.
5. Record smoke result and observed request id.
6. Delete test backup artifacts when the retention window ends.

For a real staging deployment drill, use `docs/staging-deployment-drill.md` and record the restore result in `docs/staging-deployment-drill-evidence-template.md`. The preferred restore target is a disposable local database or a temporary staging database. Do not overwrite the active staging database unless a separate restore approval exists.

## Migration Pre-Backup Flow

Before any staging or production migration:

1. Review Alembic migration files.
2. Create a PostgreSQL backup.
3. Verify checksum and file size.
4. Record backup evidence.
5. Apply migration.
6. Run health/readiness and smoke checks.
7. Check metrics and active incidents before and after migration.
8. Record migration result and rollback strategy.

If backup or verification fails, stop the release candidate and do not run the migration.

If a migration or restore is part of an active incident, use `docs/incident-evidence-template.md` in addition to backup evidence. Database restore is a separate approval path from code rollback.

## Release Checklist

- [ ] Backup created before migration.
- [ ] SHA256 checksum recorded.
- [ ] Backup file size recorded.
- [ ] Backup storage location recorded.
- [ ] Restore strategy reviewed.
- [ ] Restore drill target is safe and does not overwrite active staging data without approval.
- [ ] Staging migration rehearsed before production approval.
- [ ] Production backup evidence reviewed before production migration.
- [ ] Production backup stored encrypted outside the repository.
- [ ] No P0/P1 incident is active for the target environment before migration.
- [ ] Incident evidence is linked if backup or restore is used during recovery.

## Retention Guidance

Suggested non-production retention:

- Local: delete when no longer needed.
- Staging release candidate: keep until the release is accepted or rejected.
- Staging migration rehearsal: keep through rollback window.

Production retention must be defined outside this repository and should include encryption, access control, retention expiry, and deletion evidence.

## Privacy Deletion and Backup Residue

PR #52 adds current-user training-data deletion from the live database. That operation does not immediately remove matching historical rows from PostgreSQL backups that were created before deletion.

Operational rules:

- Backup artifacts must remain encrypted and access-controlled in production.
- Backup retention windows must be documented before real-user trials.
- A production restore can reintroduce data as of the backup timestamp, so any restore after a privacy deletion needs explicit review.
- Deletion evidence should record the live-database deletion time and the backup retention window that governs older copies.
- Do not manually edit SQL backup files to remove one user's rows unless a reviewed incident/privacy procedure requires it.

## Production Requirements

Production backup and restore are not automated by this PR.

Production must require:

- explicit human approval
- encrypted backup storage
- restricted operator access
- backup evidence
- restore plan
- rollback decision record
- no secrets or production data committed to git

Do not restore production using local convenience commands without a reviewed incident or release procedure.

## Common Failures

- `postgres` container is not running: start the target Compose stack.
- `pg_dump` fails: check database name, user, and service health.
- restore fails on SQL error: stop and inspect the failing statement before retrying.
- checksum changed unexpectedly: discard the artifact and create a new backup.
- backup appears in `git status`: move it under `backups/` or delete it; backup artifacts must not be committed.
