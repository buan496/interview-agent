"""Add scoring rubric versioning."""

from __future__ import annotations

from alembic import op


revision = "0010_scoring_rubric_versioning"
down_revision = "0009_question_bank_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE scoring_rubrics (
          id                 BIGSERIAL PRIMARY KEY,
          name               VARCHAR(120) NOT NULL UNIQUE,
          description        TEXT,
          status             VARCHAR(15) NOT NULL DEFAULT 'draft',
          created_by_user_id BIGINT NULL REFERENCES users(id),
          updated_by_user_id BIGINT NULL REFERENCES users(id),
          created_at         TIMESTAMPTZ DEFAULT now(),
          updated_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_scoring_rubrics_name ON scoring_rubrics(name)")
    op.execute("CREATE INDEX idx_scoring_rubrics_status ON scoring_rubrics(status)")

    op.execute(
        """
        CREATE TABLE scoring_rubric_versions (
          id                 BIGSERIAL PRIMARY KEY,
          rubric_id          BIGINT NOT NULL REFERENCES scoring_rubrics(id),
          version            VARCHAR(40) NOT NULL,
          dimensions_json    JSONB NOT NULL DEFAULT '[]'::jsonb,
          prompt_template    TEXT NOT NULL,
          scoring_scale      VARCHAR(40) NOT NULL DEFAULT '0-100',
          status             VARCHAR(15) NOT NULL DEFAULT 'draft',
          created_by_user_id BIGINT NULL REFERENCES users(id),
          created_at         TIMESTAMPTZ DEFAULT now(),
          published_at       TIMESTAMPTZ,
          archived_at        TIMESTAMPTZ,
          CONSTRAINT uq_rubric_version UNIQUE (rubric_id, version)
        )
        """
    )
    op.execute("CREATE INDEX idx_rubric_versions_rubric_status ON scoring_rubric_versions(rubric_id, status)")
    op.execute("CREATE INDEX idx_rubric_versions_status_created ON scoring_rubric_versions(status, created_at)")

    op.execute("ALTER TABLE questions ADD COLUMN default_rubric_version_id BIGINT NULL REFERENCES scoring_rubric_versions(id)")
    op.execute("ALTER TABLE evaluation_results ADD COLUMN rubric_version_id BIGINT NULL REFERENCES scoring_rubric_versions(id)")
    op.execute("CREATE INDEX idx_questions_default_rubric_version ON questions(default_rubric_version_id)")
    op.execute("CREATE INDEX idx_eval_rubric_version ON evaluation_results(rubric_version_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_eval_rubric_version")
    op.execute("DROP INDEX IF EXISTS idx_questions_default_rubric_version")
    op.execute("ALTER TABLE evaluation_results DROP COLUMN IF EXISTS rubric_version_id")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS default_rubric_version_id")
    op.execute("DROP INDEX IF EXISTS idx_rubric_versions_status_created")
    op.execute("DROP INDEX IF EXISTS idx_rubric_versions_rubric_status")
    op.execute("DROP TABLE IF EXISTS scoring_rubric_versions")
    op.execute("DROP INDEX IF EXISTS idx_scoring_rubrics_status")
    op.execute("DROP INDEX IF EXISTS idx_scoring_rubrics_name")
    op.execute("DROP TABLE IF EXISTS scoring_rubrics")
