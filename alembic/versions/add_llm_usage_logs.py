"""revision 0010, AI observability logs"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("llm_usage_logs",
                    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                    *[sa.Column(name, sa.VARCHAR(size), nullable=nullable) for name, size, nullable in [
                        ("operation_id", 64, False), ("module_name", 100, False), ("job_id", 64, True),
                        ("candidate_id", 64, True), ("thread_id", 100, True), ("model_name", 150, False),
                        ("pricing_version", 100, False), ("status", 20, False), ("error_type", 150, True), ("langsmith_run_id", 64, True)]],
                    *[sa.Column(name, sa.Integer(), nullable=True)
                        for name in ["input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens"]],
                    sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
                    sa.Column("latency_ms", sa.Float(), nullable=False),
                    sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
                    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
                    )
    for suffix, column in [("created", "created_at"), ("operation", "operation_id"), ("job", "job_id")]:
        op.create_index("idx_usage_"+suffix, "llm_usage_logs", [column])


def downgrade():
    op.drop_table("llm_usage_logs")
