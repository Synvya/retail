"""Migration to add private_key field to OAuthToken table."""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined, unused-ignore]

# revision identifiers, used by Alembic.
revision = "add_private_key_to_oauth_token"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add private_key column to oauth_tokens table."""
    op.add_column("oauth_tokens", sa.Column("private_key", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove private_key column from oauth_tokens table."""
    op.drop_column("oauth_tokens", "private_key")
