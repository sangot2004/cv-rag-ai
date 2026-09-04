"""
add chat_conversations table
Revision ID: 0004
Revises: 0003
Create Date: 2026-09-04"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("thread_id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "title", sa.VARCHAR(255), nullable=False, server_default="Cuộc trò chuyện mới"
        ),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        mysql_engine="InnoDB"
    )
    op.create_index("idx_chat_conversations_updated_at", "chat_conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_table("chat_conversations")
