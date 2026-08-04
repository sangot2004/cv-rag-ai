"""initial schema - 6 tables (ingestion_jobs, candidates, candidate_skills,
candidate_experience, candidate_education, candidate_chunks)

Revision ID: 0001
Revises:
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ingestion_jobs trước, CHƯA gắn FK candidate_id (vì candidates chưa tồn tại)
    op.create_table(
        "ingestion_jobs",
        sa.Column("job_id", sa.CHAR(36), primary_key=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=True),
        sa.Column("source_type", sa.VARCHAR(20), nullable=False),
        sa.Column("source_reference", sa.VARCHAR(500), nullable=True),
        sa.Column("minio_bucket", sa.VARCHAR(100), nullable=False),
        sa.Column("minio_object_key", sa.VARCHAR(500), nullable=False),
        sa.Column("original_filename", sa.VARCHAR(255), nullable=False),
        sa.Column("file_type", sa.VARCHAR(10), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.INTEGER, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.INTEGER, nullable=False, server_default="3"),
        sa.Column("error_message", sa.TEXT, nullable=True),
        sa.Column("created_at", sa.DATETIME, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DATETIME,
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_jobs_status", "ingestion_jobs", ["status"])

    # 2. candidates — FK source_job_id -> ingestion_jobs (đã tồn tại, tạo được luôn)
    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.CHAR(36), primary_key=True),
        sa.Column("full_name", sa.VARCHAR(255), nullable=False),
        sa.Column("email", sa.VARCHAR(255), nullable=True),
        sa.Column("phone", sa.VARCHAR(50), nullable=True),
        sa.Column("applied_position", sa.VARCHAR(255), nullable=True),
        sa.Column("total_years_experience", sa.FLOAT, nullable=True),
        sa.Column("raw_text", sa.TEXT, nullable=True),
        sa.Column("content_hash", sa.CHAR(64), nullable=True),
        sa.Column("source_job_id", sa.CHAR(36), nullable=False),
        sa.Column("created_at", sa.DATETIME, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DATETIME,
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["source_job_id"], ["ingestion_jobs.job_id"], name="fk_candidate_job"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_candidates_email", "candidates", ["email"])
    op.create_index("idx_candidates_content_hash", "candidates", ["content_hash"])

    # 3. Giờ candidates đã tồn tại -> thêm FK ngược lại cho ingestion_jobs.candidate_id
    op.create_foreign_key(
        "fk_job_candidate",
        "ingestion_jobs",
        "candidates",
        ["candidate_id"],
        ["candidate_id"],
    )

    # 4. Các bảng con — chỉ phụ thuộc 1 chiều vào candidates
    op.create_table(
        "candidate_skills",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("skill_name", sa.VARCHAR(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_skill_candidate"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_skill_name", "candidate_skills", ["skill_name"])

    op.create_table(
        "candidate_experience",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("company", sa.VARCHAR(255), nullable=True),
        sa.Column("title", sa.VARCHAR(255), nullable=True),
        sa.Column("start_date", sa.DATE, nullable=True),
        sa.Column("end_date", sa.DATE, nullable=True),
        sa.Column("description", sa.TEXT, nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_exp_candidate"
        ),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "candidate_education",
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("school", sa.VARCHAR(255), nullable=True),
        sa.Column("degree", sa.VARCHAR(255), nullable=True),
        sa.Column("field", sa.VARCHAR(255), nullable=True),
        sa.Column("graduation_year", sa.INTEGER, nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_edu_candidate"
        ),
        mysql_engine="InnoDB",
    )

    op.create_table(
        "candidate_chunks",
        sa.Column("chunk_id", sa.CHAR(36), primary_key=True),
        sa.Column("candidate_id", sa.CHAR(36), nullable=False),
        sa.Column("section_type", sa.VARCHAR(30), nullable=False),
        sa.Column("source_ref_id", sa.INTEGER, nullable=True),
        sa.Column("created_at", sa.DATETIME, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.candidate_id"], name="fk_chunk_candidate"
        ),
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("candidate_chunks")
    op.drop_table("candidate_education")
    op.drop_table("candidate_experience")
    op.drop_table("candidate_skills")
    op.drop_constraint("fk_job_candidate", "ingestion_jobs", type_="foreignkey")
    op.drop_table("candidates")
    op.drop_table("ingestion_jobs")
