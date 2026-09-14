"""add sent_emails table

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sent_emails",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("recipient_email", sa.VARCHAR(255), nullable=False),
        sa.Column("subject", sa.VARCHAR(500), nullable=False),
        sa.Column("body", sa.TEXT, nullable=False),
        sa.Column("gmail_message_id", sa.VARCHAR(100), nullable=True),
        sa.Column("sent_at", sa.DATETIME, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_sentemail_candidate"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_sent_emails_candidate", "sent_emails", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("sent_emails")
