"""add departments, job_postings, posting_id on candidates

Revision ID: 0005
Revises: 0004
Create Date: 2024-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("department_id", sa.CHAR(36), primary_key=True),
        sa.Column("department_name", sa.VARCHAR(100), nullable=False),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "job_postings",
        sa.Column("posting_id", sa.CHAR(36), primary_key=True),
        sa.Column("department_id", sa.CHAR(36), nullable=False),
        sa.Column("position_title", sa.VARCHAR(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.department_id"],
            name="fk_posting_dept",
        ),
        mysql_engine="InnoDB",
    )

    op.add_column("candidates", sa.Column("posting_id", sa.CHAR(36), nullable=True))
    op.create_foreign_key("fk_candidate_posting", "candidates", "job_postings", ["posting_id"], ["posting_id"])


def downgrade() -> None:
    op.drop_constraint("fk_candidate_posting", "candidates", type_="foreignkey")
    op.drop_column("candidates", "posting_id")
    op.drop_table("job_postings")
    op.drop_table("departments")
