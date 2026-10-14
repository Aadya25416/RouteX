"""phase4_data_collection_and_ingestion

Revision ID: d8e3b4a5f607
Revises: 06fe7ea60245
Create Date: 2026-10-14 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = 'd8e3b4a5f607'
down_revision: Union[str, None] = '06fe7ea60245'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend incident_evidence for unified raw evidence and ML contract
    op.alter_column('incident_evidence', 'incident_id',
                    existing_type=sa.UUID(),
                    nullable=True)
    op.add_column('incident_evidence', sa.Column('sha256_checksum', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_incident_evidence_sha256_checksum'), 'incident_evidence', ['sha256_checksum'], unique=False)
    op.add_column('incident_evidence', sa.Column('source_provider', sa.String(length=100), nullable=True))
    op.add_column('incident_evidence', sa.Column('uploader_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_incident_evidence_uploader_id', 'incident_evidence', 'users', ['uploader_id'], ['id'], ondelete='SET NULL')
    op.add_column('incident_evidence', sa.Column('road_segment_id', sa.String(length=64), nullable=True))
    op.create_foreign_key('fk_incident_evidence_road_segment_id', 'incident_evidence', 'road_segments', ['road_segment_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_incident_evidence_road_segment_id'), 'incident_evidence', ['road_segment_id'], unique=False)

    op.add_column('incident_evidence', sa.Column('location_geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False), nullable=True))
    op.create_index('idx_incident_evidence_location_geom', 'incident_evidence', ['location_geom'], unique=False, postgresql_using='gist')

    op.add_column('incident_evidence', sa.Column('footprint_geom', geoalchemy2.types.Geometry(geometry_type='GEOMETRY', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False), nullable=True))
    op.create_index('idx_incident_evidence_footprint_geom', 'incident_evidence', ['footprint_geom'], unique=False, postgresql_using='gist')

    op.add_column('incident_evidence', sa.Column('acquisition_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('incident_evidence', sa.Column('validation_status', sa.String(length=30), server_default='VALIDATED', nullable=False))
    op.add_column('incident_evidence', sa.Column('claimed_by', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_incident_evidence_claimed_by'), 'incident_evidence', ['claimed_by'], unique=False)
    op.add_column('incident_evidence', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incident_evidence', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incident_evidence', sa.Column('processing_error', sa.Text(), nullable=True))
    op.add_column('incident_evidence', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))

    # 2. Extend weather_observations
    op.add_column('weather_observations', sa.Column('wind_gusts_kmh', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('snowfall_cm', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('weather_code', sa.Integer(), nullable=True))
    op.add_column('weather_observations', sa.Column('forecast_valid_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('weather_observations', sa.Column('road_segment_id', sa.String(length=64), nullable=True))
    op.create_foreign_key('fk_weather_observations_road_segment_id', 'weather_observations', 'road_segments', ['road_segment_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_weather_observations_road_segment_id'), 'weather_observations', ['road_segment_id'], unique=False)
    op.add_column('weather_observations', sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # 3. Create traffic_observations
    op.create_table(
        'traffic_observations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('road_segment_id', sa.String(length=64), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sample_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('avg_speed_kmh', sa.Float(), nullable=True),
        sa.Column('median_speed_kmh', sa.Float(), nullable=True),
        sa.Column('congestion_ratio', sa.Float(), nullable=True),
        sa.Column('confidence', sa.String(length=30), server_default='INSUFFICIENT_DATA', nullable=False),
        sa.Column('data_freshness_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['road_segment_id'], ['road_segments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_traffic_observations_road_segment_id'), 'traffic_observations', ['road_segment_id'], unique=False)
    op.create_index(op.f('ix_traffic_observations_window_start'), 'traffic_observations', ['window_start'], unique=False)
    op.create_index(op.f('ix_traffic_observations_window_end'), 'traffic_observations', ['window_end'], unique=False)
    op.create_index('ix_traffic_observations_segment_window', 'traffic_observations', ['road_segment_id', 'window_end'], unique=False)

    # 4. Create satellite_ingestion_logs
    op.create_table(
        'satellite_ingestion_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('scene_id', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cloud_cover_percent', sa.Float(), nullable=True),
        sa.Column('footprint_geom', geoalchemy2.types.Geometry(geometry_type='GEOMETRY', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='SUCCESS', nullable=False),
        sa.Column('evidence_id', sa.UUID(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['incident_evidence.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_satellite_ingestion_logs_scene_id'), 'satellite_ingestion_logs', ['scene_id'], unique=True)
    op.create_index('idx_satellite_ingestion_logs_footprint_geom', 'satellite_ingestion_logs', ['footprint_geom'], unique=False, postgresql_using='gist')


def downgrade() -> None:
    # 4. Drop satellite_ingestion_logs
    op.drop_index('idx_satellite_ingestion_logs_footprint_geom', table_name='satellite_ingestion_logs', postgresql_using='gist')
    op.drop_index(op.f('ix_satellite_ingestion_logs_scene_id'), table_name='satellite_ingestion_logs')
    op.drop_table('satellite_ingestion_logs')

    # 3. Drop traffic_observations
    op.drop_index('ix_traffic_observations_segment_window', table_name='traffic_observations')
    op.drop_index(op.f('ix_traffic_observations_window_end'), table_name='traffic_observations')
    op.drop_index(op.f('ix_traffic_observations_window_start'), table_name='traffic_observations')
    op.drop_index(op.f('ix_traffic_observations_road_segment_id'), table_name='traffic_observations')
    op.drop_table('traffic_observations')

    # 2. Revert weather_observations
    op.drop_constraint('fk_weather_observations_road_segment_id', 'weather_observations', type_='foreignkey')
    op.drop_index(op.f('ix_weather_observations_road_segment_id'), table_name='weather_observations')
    op.drop_column('weather_observations', 'raw_payload')
    op.drop_column('weather_observations', 'road_segment_id')
    op.drop_column('weather_observations', 'forecast_valid_at')
    op.drop_column('weather_observations', 'weather_code')
    op.drop_column('weather_observations', 'snowfall_cm')
    op.drop_column('weather_observations', 'wind_gusts_kmh')

    # 1. Revert incident_evidence
    op.drop_index(op.f('ix_incident_evidence_claimed_by'), table_name='incident_evidence')
    op.drop_column('incident_evidence', 'updated_at')
    op.drop_column('incident_evidence', 'processing_error')
    op.drop_column('incident_evidence', 'processed_at')
    op.drop_column('incident_evidence', 'claimed_at')
    op.drop_column('incident_evidence', 'claimed_by')
    op.drop_column('incident_evidence', 'validation_status')
    op.drop_column('incident_evidence', 'acquisition_metadata')
    op.drop_index('idx_incident_evidence_footprint_geom', table_name='incident_evidence', postgresql_using='gist')
    op.drop_column('incident_evidence', 'footprint_geom')
    op.drop_index('idx_incident_evidence_location_geom', table_name='incident_evidence', postgresql_using='gist')
    op.drop_column('incident_evidence', 'location_geom')
    op.drop_constraint('fk_incident_evidence_road_segment_id', 'incident_evidence', type_='foreignkey')
    op.drop_index(op.f('ix_incident_evidence_road_segment_id'), table_name='incident_evidence')
    op.drop_column('incident_evidence', 'road_segment_id')
    op.drop_constraint('fk_incident_evidence_uploader_id', 'incident_evidence', type_='foreignkey')
    op.drop_column('incident_evidence', 'uploader_id')
    op.drop_column('incident_evidence', 'source_provider')
    op.drop_index(op.f('ix_incident_evidence_sha256_checksum'), table_name='incident_evidence')
    op.drop_column('incident_evidence', 'sha256_checksum')
    op.alter_column('incident_evidence', 'incident_id',
                    existing_type=sa.UUID(),
                    nullable=False)
