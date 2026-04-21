"""Add user tags table and custom_tags column

Revision ID: 003_add_user_tags
Revises: 002_create_assets
Create Date: 2024-01-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_add_user_tags"
down_revision: Union[str, None] = "002_create_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_tags table
    op.create_table(
        "user_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_tags_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
    )
    op.create_index("ix_user_tags_user_id", "user_tags", ["user_id"], unique=False)
    op.create_index("ix_user_tags_user_name", "user_tags", ["user_id", "name"], unique=False)

    # Add custom_tags column to assets table
    op.add_column("assets", sa.Column("custom_tags", sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove custom_tags column from assets
    op.drop_column("assets", "custom_tags")

    # Drop user_tags table
    op.drop_index("ix_user_tags_user_name", table_name="user_tags")
    op.drop_index("ix_user_tags_user_id", table_name="user_tags")
    op.drop_table("user_tags")
