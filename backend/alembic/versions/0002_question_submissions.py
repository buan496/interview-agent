from __future__ import annotations

from alembic import op


revision = "0002_question_submissions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE question_submissions (
          id                  BIGSERIAL PRIMARY KEY,
          submitter_name      VARCHAR(80),
          company_name        VARCHAR(100) NOT NULL,
          position_name       VARCHAR(50) NOT NULL,
          title               VARCHAR(300) NOT NULL,
          body                TEXT,
          answer_key          TEXT NOT NULL,
          difficulty          SMALLINT NOT NULL DEFAULT 3,
          qtype               VARCHAR(20) NOT NULL,
          source_type         VARCHAR(20) NOT NULL DEFAULT 'ugc',
          tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
          status              VARCHAR(20) NOT NULL DEFAULT 'pending_review',
          review_note         TEXT,
          created_question_id BIGINT REFERENCES questions(id),
          created_at          TIMESTAMPTZ DEFAULT now(),
          reviewed_at         TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_submission_status_created ON question_submissions(status, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS question_submissions")
