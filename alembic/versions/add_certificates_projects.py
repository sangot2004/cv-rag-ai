"""add candidate_certifivates and candidate_project tables
Revision ID: 0002
Revises: 0001
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_certificates",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("name", sa.VARCHAR(255), nullable=False),
        sa.Column("issuer", sa.VARCHAR(255), nullable=True),
        sa.Column("issue_date", sa.DATE, nullable=True),
        sa.Column("credential_id", sa.VARCHAR(100), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_certificate_candidate"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_certificate_name", "candidate_certificates", ["name"])

    op.create_table(
        "candidate_projects",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("name", sa.VARCHAR(255), nullable=False),
        sa.Column("role", sa.VARCHAR(255), nullable=True),
        sa.Column("tech_stack", sa.VARCHAR(500), nullable=True),
        sa.Column("description", sa.TEXT, nullable=True),
        sa.Column("start_date", sa.DATE, nullable=True),
        sa.Column("end_date", sa.DATE, nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_project_candidate"
        ),
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("candidate_projects")
    op.drop_table("candidate_certificates")
