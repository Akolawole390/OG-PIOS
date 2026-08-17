"""add email verification to users

Revision ID: a9e7334bdb53
Revises: 107095967769
Create Date: 2026-08-14 19:47:30.917099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9e7334bdb53'
down_revision: Union[str, Sequence[str], None] = '107095967769'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate proposed dropping uq_commodity_prices_commodity_date here — a recurring
    # false positive (see every migration since Production Loss). That constraint was hand-added
    # via op.create_unique_constraint rather than declared in the CommodityPrice model's
    # __table_args__, so autogenerate's model-vs-DB diff doesn't recognize it as "belonging" to
    # the model. It must never be dropped.

    # Backfill-then-diverge: every EXISTING row (already-trusted, admin-created accounts) becomes
    # true at add-time via the server_default; the immediately-following alter_column changes
    # only the default for FUTURE inserts to false, leaving existing rows untouched. No separate
    # UPDATE/table scan needed.
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('users', 'is_email_verified', server_default=sa.false())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_email_verified')
