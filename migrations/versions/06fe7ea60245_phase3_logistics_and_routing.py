"""phase3_logistics_and_routing

Revision ID: 06fe7ea60245
Revises: f465174fcaeb
Create Date: 2026-10-12 21:31:10.841862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '06fe7ea60245'
down_revision: Union[str, None] = 'f465174fcaeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deliveries
    op.add_column('deliveries', sa.Column('cargo_type', sa.String(length=50), nullable=False, server_default='GENERAL'))
    op.add_column('deliveries', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('deliveries', sa.Column('origin_name', sa.String(length=255), nullable=True))
    op.add_column('deliveries', sa.Column('destination_name', sa.String(length=255), nullable=True))
    op.alter_column('deliveries', 'priority',
               existing_type=sa.VARCHAR(length=20),
               comment='LOW, NORMAL, HIGH, CRITICAL',
               existing_comment='standard, critical, emergency',
               existing_nullable=False)
    op.create_index(op.f('ix_deliveries_cargo_type'), 'deliveries', ['cargo_type'], unique=False)
    op.create_index(op.f('ix_deliveries_priority'), 'deliveries', ['priority'], unique=False)

    # Route recommendations
    op.add_column('route_recommendations', sa.Column('ordered_node_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('route_recommendations', sa.Column('snapped_origin_node_id', sa.String(length=64), nullable=True))
    op.add_column('route_recommendations', sa.Column('snapped_destination_node_id', sa.String(length=64), nullable=True))
    op.add_column('route_recommendations', sa.Column('snapped_origin_distance_m', sa.Float(), nullable=True))
    op.add_column('route_recommendations', sa.Column('snapped_destination_distance_m', sa.Float(), nullable=True))
    op.add_column('route_recommendations', sa.Column('safety_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('route_recommendations', sa.Column('meets_safety_policy', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('route_recommendations', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.alter_column('route_recommendations', 'mode',
               existing_type=sa.VARCHAR(length=30),
               comment='SHORTEST_DISTANCE, FASTEST_SAFE',
               existing_comment='economical (shortest distance proxy), fastest_safe (emergency)',
               existing_nullable=False)

    # Trips
    op.add_column('trips', sa.Column('current_route_id', sa.UUID(), nullable=True))
    op.add_column('trips', sa.Column('estimated_duration_s', sa.Float(), nullable=True))
    op.add_column('trips', sa.Column('estimated_distance_m', sa.Float(), nullable=True))
    op.add_column('trips', sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trips', sa.Column('cancellation_reason', sa.Text(), nullable=True))
    op.alter_column('trips', 'status',
               existing_type=sa.VARCHAR(length=30),
               comment='PLANNED, IN_TRANSIT, PAUSED, COMPLETED, CANCELLED',
               existing_comment='scheduled, active, completed, cancelled',
               existing_nullable=False)
    op.create_index(op.f('ix_trips_current_route_id'), 'trips', ['current_route_id'], unique=False)
    op.create_foreign_key('fk_trips_route_recommendations', 'trips', 'route_recommendations', ['current_route_id'], ['id'], ondelete='SET NULL')

    # Vehicle locations
    op.add_column('vehicle_locations', sa.Column('trip_id', sa.UUID(), nullable=True))
    op.add_column('vehicle_locations', sa.Column('snapping_distance_m', sa.Float(), nullable=True))
    op.create_index(op.f('ix_vehicle_locations_trip_id'), 'vehicle_locations', ['trip_id'], unique=False)
    op.create_foreign_key('fk_vehicle_locations_trips', 'vehicle_locations', 'trips', ['trip_id'], ['id'], ondelete='SET NULL')

    # Vehicles
    op.add_column('vehicles', sa.Column('vehicle_code', sa.String(length=50), nullable=True))
    op.add_column('vehicles', sa.Column('status', sa.String(length=30), nullable=False, server_default='AVAILABLE'))
    op.add_column('vehicles', sa.Column('assigned_driver_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_vehicles_status'), 'vehicles', ['status'], unique=False)
    op.create_index(op.f('ix_vehicles_vehicle_code'), 'vehicles', ['vehicle_code'], unique=True)
    op.create_foreign_key('fk_vehicles_assigned_driver', 'vehicles', 'users', ['assigned_driver_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_vehicles_assigned_driver', 'vehicles', type_='foreignkey')
    op.drop_index(op.f('ix_vehicles_vehicle_code'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_status'), table_name='vehicles')
    op.drop_column('vehicles', 'assigned_driver_id')
    op.drop_column('vehicles', 'status')
    op.drop_column('vehicles', 'vehicle_code')

    op.drop_constraint('fk_vehicle_locations_trips', 'vehicle_locations', type_='foreignkey')
    op.drop_index(op.f('ix_vehicle_locations_trip_id'), table_name='vehicle_locations')
    op.drop_column('vehicle_locations', 'snapping_distance_m')
    op.drop_column('vehicle_locations', 'trip_id')

    op.drop_constraint('fk_trips_route_recommendations', 'trips', type_='foreignkey')
    op.drop_index(op.f('ix_trips_current_route_id'), table_name='trips')
    op.alter_column('trips', 'status',
               existing_type=sa.VARCHAR(length=30),
               comment='scheduled, active, completed, cancelled',
               existing_comment='PLANNED, IN_TRANSIT, PAUSED, COMPLETED, CANCELLED',
               existing_nullable=False)
    op.drop_column('trips', 'cancellation_reason')
    op.drop_column('trips', 'paused_at')
    op.drop_column('trips', 'estimated_distance_m')
    op.drop_column('trips', 'estimated_duration_s')
    op.drop_column('trips', 'current_route_id')

    op.alter_column('route_recommendations', 'mode',
               existing_type=sa.VARCHAR(length=30),
               comment='economical (shortest distance proxy), fastest_safe (emergency)',
               existing_comment='SHORTEST_DISTANCE, FASTEST_SAFE',
               existing_nullable=False)
    op.drop_column('route_recommendations', 'is_active')
    op.drop_column('route_recommendations', 'meets_safety_policy')
    op.drop_column('route_recommendations', 'safety_summary')
    op.drop_column('route_recommendations', 'snapped_destination_distance_m')
    op.drop_column('route_recommendations', 'snapped_origin_distance_m')
    op.drop_column('route_recommendations', 'snapped_destination_node_id')
    op.drop_column('route_recommendations', 'snapped_origin_node_id')
    op.drop_column('route_recommendations', 'ordered_node_ids')

    op.drop_index(op.f('ix_deliveries_priority'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_cargo_type'), table_name='deliveries')
    op.alter_column('deliveries', 'priority',
               existing_type=sa.VARCHAR(length=20),
               comment='standard, critical, emergency',
               existing_comment='LOW, NORMAL, HIGH, CRITICAL',
               existing_nullable=False)
    op.drop_column('deliveries', 'destination_name')
    op.drop_column('deliveries', 'origin_name')
    op.drop_column('deliveries', 'description')
    op.drop_column('deliveries', 'cargo_type')
