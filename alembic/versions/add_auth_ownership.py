"""Login sessions and conversation ownership. Legacy conversations stay unassigned."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("app_users",
                    sa.Column("user_id", sa.CHAR(36), primary_key=True),
                    sa.Column("username", sa.String(100), nullable=False, unique=True),
                    sa.Column("password_hash", sa.String(255), nullable=False),
                    sa.Column("role", sa.String(20), nullable=False),
                    sa.Column("department_id", sa.CHAR(36), sa.ForeignKey("departments.department_id")),
                    sa.Column("is_active", sa.Boolean(), nullable=False),
                    sa.Column("failed_attempts", sa.Integer(), nullable=False),
                    sa.Column("locked_until", sa.DateTime()),
                    sa.Column("created_at", sa.DateTime(), nullable=False))

    op.create_table("auth_sessions",
                    sa.Column("token_hash", sa.CHAR(64), primary_key=True),
                    sa.Column("user_id", sa.CHAR(36), sa.ForeignKey("app_users.user_id"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(), nullable=False))

    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    with op.batch_alter_table("chat_conversations") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.CHAR(36), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_chat_owner", "app_users", ["owner_user_id"], ["user_id"])
        batch.create_index("ix_chat_conversations_owner_user_id", ["owner_user_id"])


def downgrade():
    with op.batch_alter_table("chat_conversations") as batch:
        batch.drop_index("ix_chat_conversations_owner_user_id")
        batch.drop_constraint("fk_chat_owner", type_="foreignkey")
        batch.drop_column("deleted_at")
        batch.drop_column("owner_user_id")

    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("app_users")
