"""add production loss fields and commodity price constraint

Revision ID: 9ec63324886e
Revises: ef2abc3c147d
Create Date: 2026-08-10 10:19:36.755745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ec63324886e'
down_revision: Union[str, Sequence[str], None] = 'ef2abc3c147d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('production_losses', sa.Column('estimated_mscf_lost', sa.Float(), nullable=True))
    op.add_column('production_losses', sa.Column('currency', sa.String(length=10), nullable=True))
    op.add_column('production_losses', sa.Column('category', sa.String(length=50), nullable=True))
    op.add_column('production_losses', sa.Column('downtime_hours', sa.Float(), nullable=True))
    op.add_column('production_losses', sa.Column('maintenance_record_id', sa.Integer(), nullable=True))
    op.alter_column('production_losses', 'estimated_bopd_lost',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.create_foreign_key(
        'fk_production_losses_maintenance_record_id',
        'production_losses', 'maintenance_records', ['maintenance_record_id'], ['id'],
    )

    # Data-integrity fix: commodity_prices is currently unused (zero rows) so this is a safe
    # additive constraint — prevents ambiguous duplicate price rows for the same commodity/day
    # once the Production Loss module starts writing to it. Same "legitimate additive
    # migration" precedent as Production's (well_id, record_date) constraint.
    op.create_unique_constraint(
        'uq_commodity_prices_commodity_date', 'commodity_prices', ['commodity', 'effective_date']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_commodity_prices_commodity_date', 'commodity_prices', type_='unique')
    op.drop_constraint('fk_production_losses_maintenance_record_id', 'production_losses', type_='foreignkey')
    op.alter_column('production_losses', 'estimated_bopd_lost',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.drop_column('production_losses', 'maintenance_record_id')
    op.drop_column('production_losses', 'downtime_hours')
    op.drop_column('production_losses', 'category')
    op.drop_column('production_losses', 'currency')
    op.drop_column('production_losses', 'estimated_mscf_lost')
