"""add maintenance work orders and scheduling fields

Revision ID: ef2abc3c147d
Revises: 3b9c217baa6d
Create Date: 2026-08-10 07:06:26.712622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef2abc3c147d'
down_revision: Union[str, Sequence[str], None] = '3b9c217baa6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SETTINGS_TABLE = sa.table(
    "system_settings",
    sa.column("key", sa.String),
    sa.column("value", sa.String),
    sa.column("description", sa.String),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('equipment', sa.Column('maintenance_frequency_days', sa.Integer(), nullable=True))
    op.add_column('maintenance_records', sa.Column('work_order_number', sa.String(length=20), nullable=True))
    # server_default backfills existing rows atomically with the ADD COLUMN — matches the
    # ORM-level Python default declared on MaintenanceRecord.priority.
    op.add_column(
        'maintenance_records',
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),
    )
    op.add_column('maintenance_records', sa.Column('planned_start_date', sa.Date(), nullable=True))
    op.add_column('maintenance_records', sa.Column('planned_completion_date', sa.Date(), nullable=True))
    op.add_column('maintenance_records', sa.Column('labor_cost', sa.Float(), nullable=True))
    op.add_column('maintenance_records', sa.Column('parts_cost', sa.Float(), nullable=True))
    op.add_column('maintenance_records', sa.Column('contractor_cost', sa.Float(), nullable=True))
    op.add_column('maintenance_records', sa.Column('other_cost', sa.Float(), nullable=True))
    op.add_column('maintenance_records', sa.Column('downtime_hours', sa.Float(), nullable=True))
    op.add_column('maintenance_records', sa.Column('failure_cause', sa.String(length=500), nullable=True))
    op.add_column('maintenance_records', sa.Column('corrective_action', sa.Text(), nullable=True))
    op.add_column('maintenance_records', sa.Column('notes', sa.Text(), nullable=True))
    op.create_unique_constraint(
        'uq_maintenance_records_work_order_number', 'maintenance_records', ['work_order_number']
    )

    # Defensive backfill: any pre-existing rows (from before this module existed) get a
    # deterministic work order number derived from their id, so every row satisfies the
    # frontend's assumption that a work order always has a number.
    op.execute(
        "UPDATE maintenance_records SET work_order_number = 'WO-' || lpad(id::text, 6, '0') "
        "WHERE work_order_number IS NULL"
    )

    # App config (not demo data) — seeded via the migration itself, same pattern as
    # boe_gas_factor_scf_per_bbl and equipment_health_operating_hours_threshold.
    op.bulk_insert(
        SETTINGS_TABLE,
        [
            {
                "key": "maintenance_schedule_lookahead_days",
                "value": "30",
                "description": (
                    "Number of days ahead of today's date that counts as 'upcoming' "
                    "maintenance on the scheduling view, vs. overdue (past due) or due today."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM system_settings WHERE key = 'maintenance_schedule_lookahead_days'")
    op.drop_constraint('uq_maintenance_records_work_order_number', 'maintenance_records', type_='unique')
    op.drop_column('maintenance_records', 'notes')
    op.drop_column('maintenance_records', 'corrective_action')
    op.drop_column('maintenance_records', 'failure_cause')
    op.drop_column('maintenance_records', 'downtime_hours')
    op.drop_column('maintenance_records', 'other_cost')
    op.drop_column('maintenance_records', 'contractor_cost')
    op.drop_column('maintenance_records', 'parts_cost')
    op.drop_column('maintenance_records', 'labor_cost')
    op.drop_column('maintenance_records', 'planned_completion_date')
    op.drop_column('maintenance_records', 'planned_start_date')
    op.drop_column('maintenance_records', 'priority')
    op.drop_column('maintenance_records', 'work_order_number')
    op.drop_column('equipment', 'maintenance_frequency_days')
