"""Add user role for RBAC v1."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_user_role_rbac"
down_revision = "0007_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=30), nullable=False, server_default="user"))
    op.create_index("idx_users_role", "users", ["role"])
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_users_role", table_name="users")
    op.drop_column("users", "role")
