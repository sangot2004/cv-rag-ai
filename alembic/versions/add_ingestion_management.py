"""Upload assignment, file deduplication and observable ingestion jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ingestion_jobs") as batch:
        batch.add_column(sa.Column("error_code", sa.String(64)))
        batch.add_column(sa.Column("dispatch_error", sa.String(64)))
        batch.add_column(sa.Column("file_hash", sa.CHAR(64)))
        batch.add_column(sa.Column("posting_id", sa.CHAR(36)))
        batch.add_column(sa.Column("uploaded_by", sa.CHAR(36)))
        batch.add_column(sa.Column("started_at", sa.DateTime()))
        batch.create_unique_constraint("uq_ingestion_file_hash", ["file_hash"])
        batch.create_foreign_key("fk_ingestion_posting", "job_postings", ["posting_id"], ["posting_id"])
        batch.create_foreign_key("fk_ingestion_uploader", "app_users", ["uploaded_by"], ["user_id"])


def downgrade():
    with op.batch_alter_table("ingestion_jobs") as batch:
        batch.drop_constraint("fk_ingestion_uploader", type_="foreignkey")
        batch.drop_constraint("fk_ingestion_posting", type_="foreignkey")
        batch.drop_constraint("uq_ingestion_file_hash", type_="unique")
        for name in ("started_at", "uploaded_by", "posting_id", "file_hash", "dispatch_error", "error_code"):
            batch.drop_column(name)
