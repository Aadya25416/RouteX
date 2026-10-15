"""phase7_alerts_and_dashboard

Revision ID: 7a8b9c0d1e2f
Revises: 00bb6c356bdd
Create Date: 2026-10-15 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = '00bb6c356bdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add actionable alert metadata, entity association, and acknowledgement audit fields
    op.add_column('alerts', sa.Column('entity_type', sa.String(length=50), nullable=True))
    op.add_column('alerts', sa.Column('entity_id', sa.String(length=100), nullable=True))
    op.add_column('alerts', sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('alerts', sa.Column('dedup_key', sa.String(length=200), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_by_id', sa.UUID(), nullable=True))

    op.create_foreign_key(
        'fk_alerts_acknowledged_by_id_users',
        'alerts',
        'users',
        ['acknowledged_by_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.create_index(op.f('ix_alerts_entity_type'), 'alerts', ['entity_type'], unique=False)
    op.create_index(op.f('ix_alerts_entity_id'), 'alerts', ['entity_id'], unique=False)
    op.create_index(op.f('ix_alerts_dedup_key'), 'alerts', ['dedup_key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_alerts_dedup_key'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_entity_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_entity_type'), table_name='alerts')
    op.drop_constraint('fk_alerts_acknowledged_by_id_users', 'alerts', type_='foreignkey')
    op.drop_column('alerts', 'acknowledged_by_id')
    op.drop_column('alerts', 'acknowledged_at')
    op.drop_column('alerts', 'dedup_key')
    op.drop_column('alerts', 'details')
    op.drop_column('alerts', 'entity_id')
    op.drop_column('alerts', 'entity_type')
