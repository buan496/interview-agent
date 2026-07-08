"""Add question bank management fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_question_bank_management"
down_revision = "0008_user_role_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("questions", sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("questions", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.add_column("questions", sa.Column("published_at", sa.DateTime(), nullable=True))
    op.add_column("questions", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_questions_created_by_user", "questions", "users", ["created_by_user_id"], ["id"])
    op.create_foreign_key("fk_questions_updated_by_user", "questions", "users", ["updated_by_user_id"], ["id"])
    op.create_index("idx_questions_status_updated", "questions", ["status", "updated_at"])
    op.create_index("idx_questions_created_by", "questions", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("idx_questions_created_by", table_name="questions")
    op.drop_index("idx_questions_status_updated", table_name="questions")
    op.drop_constraint("fk_questions_updated_by_user", "questions", type_="foreignkey")
    op.drop_constraint("fk_questions_created_by_user", "questions", type_="foreignkey")
    op.drop_column("questions", "archived_at")
    op.drop_column("questions", "published_at")
    op.drop_column("questions", "updated_at")
    op.drop_column("questions", "updated_by_user_id")
    op.drop_column("questions", "created_by_user_id")
