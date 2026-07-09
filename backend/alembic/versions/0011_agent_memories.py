"""Add agent memories."""

from __future__ import annotations

from alembic import op


revision = "0011_agent_memories"
down_revision = "0010_scoring_rubric_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_memories (
          id             BIGSERIAL PRIMARY KEY,
          user_id        BIGINT NOT NULL REFERENCES users(id),
          memory_type    VARCHAR(30) NOT NULL,
          title          VARCHAR(200) NOT NULL,
          summary        TEXT NOT NULL,
          tags_json      JSONB NOT NULL DEFAULT '[]'::jsonb,
          evidence_json  JSONB NOT NULL DEFAULT '[]'::jsonb,
          confidence     NUMERIC(4, 2) NOT NULL DEFAULT 0.50,
          status         VARCHAR(15) NOT NULL DEFAULT 'active',
          source_type    VARCHAR(30) NOT NULL DEFAULT 'system_rule',
          source_id      BIGINT,
          first_seen_at  TIMESTAMPTZ DEFAULT now(),
          last_seen_at   TIMESTAMPTZ DEFAULT now(),
          created_at     TIMESTAMPTZ DEFAULT now(),
          updated_at     TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_agent_memories_user_status ON agent_memories(user_id, status)")
    op.execute("CREATE INDEX idx_agent_memories_user_type ON agent_memories(user_id, memory_type)")
    op.execute("CREATE INDEX idx_agent_memories_user_last_seen ON agent_memories(user_id, last_seen_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_agent_memories_user_last_seen")
    op.execute("DROP INDEX IF EXISTS idx_agent_memories_user_type")
    op.execute("DROP INDEX IF EXISTS idx_agent_memories_user_status")
    op.execute("DROP TABLE IF EXISTS agent_memories")
