from __future__ import annotations

from alembic import op


revision = "0006_llm_usage_records"
down_revision = "0005_evaluation_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE llm_usage_records (
          id                BIGSERIAL PRIMARY KEY,
          user_id           BIGINT NOT NULL REFERENCES users(id),
          session_id        BIGINT NULL REFERENCES sessions(id),
          request_id        VARCHAR(80),
          feature           VARCHAR(30) NOT NULL DEFAULT 'unknown',
          provider          VARCHAR(30) NOT NULL DEFAULT 'unknown',
          model             VARCHAR(80) NOT NULL DEFAULT 'unknown',
          prompt_tokens     INTEGER NOT NULL DEFAULT 0,
          completion_tokens INTEGER NOT NULL DEFAULT 0,
          total_tokens      INTEGER NOT NULL DEFAULT 0,
          estimated_cost    NUMERIC(12, 6) NOT NULL DEFAULT 0,
          currency          VARCHAR(3) NOT NULL DEFAULT 'USD',
          pricing_version   VARCHAR(40) NOT NULL,
          latency_ms        INTEGER,
          status            VARCHAR(15) NOT NULL DEFAULT 'success',
          error_type        VARCHAR(80),
          created_at        TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_llm_usage_user_created ON llm_usage_records(user_id, created_at)")
    op.execute("CREATE INDEX idx_llm_usage_user_feature ON llm_usage_records(user_id, feature)")
    op.execute("CREATE INDEX idx_llm_usage_request_id ON llm_usage_records(request_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_llm_usage_request_id")
    op.execute("DROP INDEX IF EXISTS idx_llm_usage_user_feature")
    op.execute("DROP INDEX IF EXISTS idx_llm_usage_user_created")
    op.execute("DROP TABLE IF EXISTS llm_usage_records")
