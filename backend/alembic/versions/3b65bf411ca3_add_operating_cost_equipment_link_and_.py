"""add operating cost equipment link and detail fields

Revision ID: 3b65bf411ca3
Revises: 9ec63324886e
Create Date: 2026-08-10 10:57:46.339658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b65bf411ca3'
down_revision: Union[str, Sequence[str], None] = '9ec63324886e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also proposed dropping 'uq_commodity_prices_commodity_date' — a false
    # positive, since that constraint was added via a hand-written op.create_unique_constraint
    # in the Production Loss module's migration rather than declared in the ORM model's
    # __table_args__, so autogenerate's diff doesn't see it as "belonging" to the model. It's
    # real, correct, load-bearing DB state (prevents ambiguous duplicate commodity/date price
    # rows) and must NOT be dropped here — intentionally omitted.
    op.add_column('operating_costs', sa.Column('description', sa.String(length=500), nullable=True))
    op.add_column('operating_costs', sa.Column('cost_period', sa.String(length=20), nullable=True))
    op.add_column('operating_costs', sa.Column('source', sa.String(length=100), nullable=True))
    op.add_column('operating_costs', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('operating_costs', sa.Column('equipment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_operating_costs_equipment_id', 'operating_costs', 'equipment', ['equipment_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_operating_costs_equipment_id', 'operating_costs', type_='foreignkey')
    op.drop_column('operating_costs', 'equipment_id')
    op.drop_column('operating_costs', 'notes')
    op.drop_column('operating_costs', 'source')
    op.drop_column('operating_costs', 'cost_period')
    op.drop_column('operating_costs', 'description')
