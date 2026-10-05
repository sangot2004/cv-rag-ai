"""Versioned optimization and activation pointer"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ops_optimization_configs",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("settings_json", sa.Text(), nullable=False),
                    sa.Column("report_json", sa.Text()),
                    sa.Column("status", sa.String(24), nullable=False),
                    sa.Column("created_at", sa.DateTime(), nullable=False)
                    )
    table = op.create_table("ops_optimization_pointer",
                            sa.Column("id", sa.Integer(), primary_key=True),
                            sa.Column("config_id", sa.String(36))
                            )
    op.bulk_insert(table, [{"id": 1, "config_id": None}])


def downgrade():
    op.drop_table("ops_optimization_pointer")
    op.drop_table("ops_optimization_configs")
