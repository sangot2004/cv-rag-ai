"""add chat_feedback table

Revision ID: 0006
Revises: 0005
Create Date: 2024-09-07
"""

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_feedback",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.CHAR(36), nullable=False),
        sa.Column("question", sa.TEXT, nullable=False),
        sa.Column("answer", sa.TEXT, nullable=False),
        sa.Column("feedback", sa.VARCHAR(10), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_chat_feedback_thread", "chat_feedback", ["thread_id"])


def downgrade() -> None:
    op.drop_table("chat_feedback")
