"""Create assets table

Revision ID: 002_create_assets
Revises: 001_create_users_and_api_keys
Create Date: 2024-01-20 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_create_assets"
down_revision: Union[str, None] = "001_create_users_and_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the assets table."""
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # File information
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        # Image dimensions
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        # Processing status
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        # ML-extracted features
        sa.Column("ml_labels", sa.Text(), nullable=True),
        sa.Column("ml_colors", sa.Text(), nullable=True),
        sa.Column("ml_text", sa.Text(), nullable=True),
        sa.Column("embedding_vector", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_assets_user_id_users",
            ondelete="CASCADE",
        ),
    )

    # Indexes for common queries
    op.create_index("ix_assets_user_id", "assets", ["user_id"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_user_status", "assets", ["user_id", "status"])
    op.create_index("ix_assets_user_created", "assets", ["user_id", "created_at"])


def downgrade() -> None:
    """Drop the assets table."""
    op.drop_index("ix_assets_user_created", "assets")
    op.drop_index("ix_assets_user_status", "assets")
    op.drop_index("ix_assets_status", "assets")
    op.drop_index("ix_assets_user_id", "assets")
    op.drop_table("assets")
