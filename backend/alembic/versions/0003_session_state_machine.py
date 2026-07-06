from __future__ import annotations

from alembic import op


revision = "0003_session_state_machine"
down_revision = "0002_question_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sessions
          ADD COLUMN deadline_at TIMESTAMPTZ,
          ADD COLUMN finished_at TIMESTAMPTZ,
          ADD COLUMN expired_at TIMESTAMPTZ,
          ADD COLUMN current_question_id BIGINT REFERENCES questions(id),
          ADD COLUMN current_question_index SMALLINT NOT NULL DEFAULT 1,
          ADD COLUMN total_questions SMALLINT NOT NULL DEFAULT 1,
          ADD COLUMN max_followups SMALLINT NOT NULL DEFAULT 3,
          ADD COLUMN current_followups SMALLINT NOT NULL DEFAULT 0,
          ADD COLUMN end_reason VARCHAR(30),
          ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now()
        """
    )
    op.execute("UPDATE sessions SET status = 'ongoing' WHERE status IS NULL OR status = ''")
    op.execute(
        """
        ALTER TABLE session_questions
          ADD COLUMN status VARCHAR(15) NOT NULL DEFAULT 'pending',
          ADD COLUMN started_at TIMESTAMPTZ,
          ADD COLUMN submitted_at TIMESTAMPTZ,
          ADD COLUMN scored_at TIMESTAMPTZ,
          ADD COLUMN answer_text TEXT,
          ADD COLUMN verdict JSONB,
          ADD COLUMN followup_count SMALLINT NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        UPDATE session_questions
        SET status = CASE WHEN final_score IS NULL THEN 'answering' ELSE 'scored' END,
            scored_at = finished_at
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE session_questions
          DROP COLUMN IF EXISTS followup_count,
          DROP COLUMN IF EXISTS verdict,
          DROP COLUMN IF EXISTS answer_text,
          DROP COLUMN IF EXISTS scored_at,
          DROP COLUMN IF EXISTS submitted_at,
          DROP COLUMN IF EXISTS started_at,
          DROP COLUMN IF EXISTS status
        """
    )
    op.execute(
        """
        ALTER TABLE sessions
          DROP COLUMN IF EXISTS updated_at,
          DROP COLUMN IF EXISTS end_reason,
          DROP COLUMN IF EXISTS current_followups,
          DROP COLUMN IF EXISTS max_followups,
          DROP COLUMN IF EXISTS total_questions,
          DROP COLUMN IF EXISTS current_question_index,
          DROP COLUMN IF EXISTS current_question_id,
          DROP COLUMN IF EXISTS expired_at,
          DROP COLUMN IF EXISTS finished_at,
          DROP COLUMN IF EXISTS deadline_at
        """
    )
