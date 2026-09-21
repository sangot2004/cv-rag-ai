"""extend sent_emails with status, error_message, batch_id

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sent_emails",
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="success"),
    )
    op.add_column("sent_emails", sa.Column("error_message", sa.TEXT, nullable=True))
    op.add_column("sent_emails", sa.Column("batch_id", sa.CHAR(36), nullable=True))
    op.create_index("idx_sent_emails_batch", "sent_emails", ["batch_id"])


def downgrade() -> None:
    op.drop_index("idx_sent_emails_batch", table_name="sent_emails")
    op.drop_column("sent_emails", "batch_id")
    op.drop_column("sent_emails", "error_message")
    op.drop_column("sent_emails", "status")
