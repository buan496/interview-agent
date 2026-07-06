from __future__ import annotations

from alembic import op


revision = "0004_practice_plans"
down_revision = "0003_session_state_machine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE practice_plans (
          id                 BIGSERIAL PRIMARY KEY,
          user_id            BIGINT NOT NULL REFERENCES users(id),
          plan_date          DATE NOT NULL,
          recommended_tasks  JSONB NOT NULL DEFAULT '[]'::jsonb,
          weak_tags          JSONB NOT NULL DEFAULT '[]'::jsonb,
          target_abilities   JSONB NOT NULL DEFAULT '[]'::jsonb,
          generated_reason   TEXT NOT NULL,
          completed          BOOLEAN NOT NULL DEFAULT false,
          created_at         TIMESTAMPTZ DEFAULT now(),
          updated_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX idx_practice_plan_user_date ON practice_plans(user_id, plan_date)")
    op.execute("CREATE INDEX idx_practice_plan_completed ON practice_plans(user_id, completed)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_practice_plan_completed")
    op.execute("DROP INDEX IF EXISTS idx_practice_plan_user_date")
    op.execute("DROP TABLE IF EXISTS practice_plans")
