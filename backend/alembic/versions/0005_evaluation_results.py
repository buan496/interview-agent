from __future__ import annotations

from alembic import op


revision = "0005_evaluation_results"
down_revision = "0004_practice_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evaluation_results (
          id                    BIGSERIAL PRIMARY KEY,
          user_id               BIGINT NOT NULL REFERENCES users(id),
          session_id            BIGINT NOT NULL REFERENCES sessions(id),
          sq_id                 BIGINT NOT NULL REFERENCES session_questions(id),
          question_id           BIGINT NOT NULL REFERENCES questions(id),
          score                 SMALLINT NOT NULL,
          mastery               VARCHAR(10) NOT NULL,
          verdict               TEXT NOT NULL,
          strengths             JSONB NOT NULL DEFAULT '[]'::jsonb,
          missing_points        JSONB NOT NULL DEFAULT '[]'::jsonb,
          expression_issues     JSONB NOT NULL DEFAULT '[]'::jsonb,
          followup_failures     JSONB NOT NULL DEFAULT '[]'::jsonb,
          action_items          JSONB NOT NULL DEFAULT '[]'::jsonb,
          recommended_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
          raw_model_output      JSONB NOT NULL DEFAULT '{}'::jsonb,
          model_name            VARCHAR(80) NOT NULL DEFAULT 'local-fallback',
          prompt_version        VARCHAR(40) NOT NULL DEFAULT 'interviewer-v1',
          created_at            TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_eval_user_created ON evaluation_results(user_id, created_at)")
    op.execute("CREATE INDEX idx_eval_session_question ON evaluation_results(session_id, sq_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_eval_session_question")
    op.execute("DROP INDEX IF EXISTS idx_eval_user_created")
    op.execute("DROP TABLE IF EXISTS evaluation_results")
