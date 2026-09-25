"""add interview_questions table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("question_text", sa.TEXT, nullable=False),
        sa.Column("category", sa.VARCHAR(30), nullable=False),
        sa.Column("evidence_quote", sa.TEXT, nullable=False),
        sa.Column("cv_section", sa.VARCHAR(100), nullable=False),
        sa.Column("created_at", sa.DATETIME, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_interview_question_candidate"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_interview_questions_candidate", "interview_questions", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("interview_questions")
