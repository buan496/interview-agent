"""Add async jobs."""

from __future__ import annotations

from alembic import op


revision = "0012_async_jobs"
down_revision = "0011_agent_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE async_jobs (
          id              BIGSERIAL PRIMARY KEY,
          job_type        VARCHAR(40) NOT NULL,
          user_id         BIGINT NOT NULL REFERENCES users(id),
          status          VARCHAR(20) NOT NULL DEFAULT 'queued',
          payload_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
          result_json     JSONB,
          error_type      VARCHAR(120),
          error_message   TEXT,
          attempts        INTEGER NOT NULL DEFAULT 0,
          max_attempts    INTEGER NOT NULL DEFAULT 3,
          idempotency_key VARCHAR(120),
          created_at      TIMESTAMPTZ DEFAULT now(),
          started_at      TIMESTAMPTZ,
          finished_at     TIMESTAMPTZ,
          updated_at      TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_async_jobs_user_created ON async_jobs(user_id, created_at)")
    op.execute("CREATE INDEX idx_async_jobs_status_created ON async_jobs(status, created_at)")
    op.execute("CREATE INDEX idx_async_jobs_type_status ON async_jobs(job_type, status)")
    op.execute("CREATE INDEX idx_async_jobs_idempotency_key ON async_jobs(idempotency_key)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_async_jobs_idempotency_key")
    op.execute("DROP INDEX IF EXISTS idx_async_jobs_type_status")
    op.execute("DROP INDEX IF EXISTS idx_async_jobs_status_created")
    op.execute("DROP INDEX IF EXISTS idx_async_jobs_user_created")
    op.execute("DROP TABLE IF EXISTS async_jobs")
