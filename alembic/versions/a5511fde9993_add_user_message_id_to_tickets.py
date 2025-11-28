"""add_user_message_id_to_tickets

Revision ID: a5511fde9993
Revises: 885185494c2c
Create Date: 2025-11-27 10:01:03.262377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5511fde9993'
down_revision: Union[str, Sequence[str], None] = '885185494c2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tickets', sa.Column('user_message_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tickets', 'user_message_id')
