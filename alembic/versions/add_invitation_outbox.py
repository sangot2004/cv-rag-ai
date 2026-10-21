"""Persistent invitation drafts, approvals and delivery outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("invitation_recipient_guards", sa.Column("recipient_email", sa.String(255), primary_key=True))
    op.create_table("invitation_batches",
        sa.Column("batch_id", sa.CHAR(36), primary_key=True),
        sa.Column("request_id", sa.CHAR(36), unique=True, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.CHAR(36), sa.ForeignKey("app_users.user_id"), nullable=False),
        sa.Column("approved_by", sa.CHAR(36), sa.ForeignKey("app_users.user_id")),
        sa.Column("kind", sa.String(10), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.String(255), nullable=False), sa.Column("interview_details", sa.Text(), nullable=False),
        sa.Column("approval_hash", sa.String(64)), sa.Column("dispatch_error", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("invitation_drafts",
        sa.Column("draft_id", sa.CHAR(36), primary_key=True),
        sa.Column("batch_id", sa.CHAR(36), sa.ForeignKey("invitation_batches.batch_id"), nullable=False),
        sa.Column("candidate_id", sa.CHAR(36), sa.ForeignKey("candidates.candidate_id"), nullable=False),
        sa.Column("recipient_email", sa.String(255)), sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)))
    op.create_index("ix_invitation_drafts_batch_id", "invitation_drafts", ["batch_id"])
    op.create_table("invitation_deliveries",
        sa.Column("delivery_id", sa.CHAR(36), primary_key=True),
        sa.Column("batch_id", sa.CHAR(36), sa.ForeignKey("invitation_batches.batch_id"), nullable=False),
        sa.Column("draft_id", sa.CHAR(36), sa.ForeignKey("invitation_drafts.draft_id"), unique=True, nullable=False),
        sa.Column("candidate_id", sa.CHAR(36), sa.ForeignKey("candidates.candidate_id"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False), sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("gmail_message_id", sa.String(100)),
        sa.Column("error_code", sa.String(64)), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()))
    op.create_index("ix_invitation_deliveries_batch_id", "invitation_deliveries", ["batch_id"])
    op.create_index("ix_invitation_deliveries_status", "invitation_deliveries", ["status"])
    with op.batch_alter_table("sent_emails") as batch:
        batch.add_column(sa.Column("delivery_id", sa.CHAR(36)))
        batch.create_foreign_key("fk_sent_email_delivery", "invitation_deliveries", ["delivery_id"], ["delivery_id"])
        batch.create_unique_constraint("uq_sent_email_delivery", ["delivery_id"])


def downgrade():
    with op.batch_alter_table("sent_emails") as batch:
        batch.drop_constraint("uq_sent_email_delivery", type_="unique")
        batch.drop_constraint("fk_sent_email_delivery", type_="foreignkey")
        batch.drop_column("delivery_id")
    op.drop_table("invitation_deliveries")
    op.drop_table("invitation_drafts")
    op.drop_table("invitation_batches")
    op.drop_table("invitation_recipient_guards")
