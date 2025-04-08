"""add_private_key_column

Revision ID: a95218b29123
Revises:
Create Date: 2024-04-07 23:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a95218b29123"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add private_key column to oauth_tokens table
    op.add_column("oauth_tokens", sa.Column("private_key", sa.String(), nullable=True))


def downgrade() -> None:
    # Remove private_key column from oauth_tokens table
    op.drop_column("oauth_tokens", "private_key")
