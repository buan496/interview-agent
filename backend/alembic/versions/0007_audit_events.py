from __future__ import annotations

from alembic import op


revision = "0007_audit_events"
down_revision = "0006_llm_usage_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_events (
          id                 BIGSERIAL PRIMARY KEY,
          actor_user_id      BIGINT NULL REFERENCES users(id),
          actor_phone_masked VARCHAR(20),
          actor_role         VARCHAR(20) NOT NULL DEFAULT 'anonymous',
          action             VARCHAR(50) NOT NULL,
          resource_type      VARCHAR(50),
          resource_id        VARCHAR(80),
          target_user_id     BIGINT NULL REFERENCES users(id),
          request_id         VARCHAR(80),
          status             VARCHAR(20) NOT NULL,
          reason             VARCHAR(120),
          ip_address         VARCHAR(80),
          user_agent         VARCHAR(300),
          metadata_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_audit_actor_created ON audit_events(actor_user_id, created_at)")
    op.execute("CREATE INDEX idx_audit_action_created ON audit_events(action, created_at)")
    op.execute("CREATE INDEX idx_audit_request_id ON audit_events(request_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audit_request_id")
    op.execute("DROP INDEX IF EXISTS idx_audit_action_created")
    op.execute("DROP INDEX IF EXISTS idx_audit_actor_created")
    op.execute("DROP TABLE IF EXISTS audit_events")
