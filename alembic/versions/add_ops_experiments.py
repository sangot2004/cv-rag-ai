"""Durable experiment jobs."""
from alembic import op
import sqlalchemy as sa
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ops_experiment_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("dataset", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(64)), sa.Column("report_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_ops_experiment_jobs_proposal_id", "ops_experiment_jobs", ["proposal_id"])


def downgrade():
    op.drop_table("ops_experiment_jobs")
