"""phase6_weather_pipeline_and_forecasts

Revision ID: 00bb6c356bdd
Revises: 5cfa804483b8
Create Date: 2026-10-14 23:37:52.772189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00bb6c356bdd'
down_revision: Union[str, None] = '5cfa804483b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add coordinates and classification fields
    op.add_column('weather_observations', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('data_type', sa.String(length=20), server_default='CURRENT', nullable=False))
    op.add_column('weather_observations', sa.Column('issue_time', sa.DateTime(timezone=True), nullable=True))

    # 2. Add meteorological measurement and forecast fields
    op.add_column('weather_observations', sa.Column('precipitation_mm', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('rain_mm', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('showers_mm', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('precipitation_probability_pct', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('relative_humidity_pct', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('dew_point_c', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('apparent_temperature_c', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('pressure_msl_hpa', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('surface_pressure_hpa', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('wind_direction_deg', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('cloud_cover_pct', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('et0_evapotranspiration_mm', sa.Float(), nullable=True))
    op.add_column('weather_observations', sa.Column('soil_moisture_m3m3', sa.Float(), nullable=True))

    # 3. Backfill coordinates and precipitation for existing records
    op.execute("UPDATE weather_observations SET latitude = ST_Y(location_geom::geometry), longitude = ST_X(location_geom::geometry) WHERE latitude IS NULL")
    op.execute("UPDATE weather_observations SET precipitation_mm = rainfall_mm WHERE precipitation_mm IS NULL AND rainfall_mm IS NOT NULL")
    op.execute("UPDATE weather_observations SET data_type = 'CURRENT' WHERE data_type IS NULL")

    # 4. Create performance and query indexes
    op.create_index('ix_weather_observations_data_type', 'weather_observations', ['data_type'], unique=False)
    op.create_index('ix_weather_observations_forecast_valid_at', 'weather_observations', ['forecast_valid_at'], unique=False)
    op.create_index('ix_weather_observations_lookup', 'weather_observations', ['provider', 'data_type', 'forecast_valid_at'], unique=False)
    op.create_index('ix_weather_observations_coords', 'weather_observations', ['latitude', 'longitude'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_weather_observations_coords', table_name='weather_observations')
    op.drop_index('ix_weather_observations_lookup', table_name='weather_observations')
    op.drop_index('ix_weather_observations_forecast_valid_at', table_name='weather_observations')
    op.drop_index('ix_weather_observations_data_type', table_name='weather_observations')

    op.drop_column('weather_observations', 'soil_moisture_m3m3')
    op.drop_column('weather_observations', 'et0_evapotranspiration_mm')
    op.drop_column('weather_observations', 'cloud_cover_pct')
    op.drop_column('weather_observations', 'wind_direction_deg')
    op.drop_column('weather_observations', 'surface_pressure_hpa')
    op.drop_column('weather_observations', 'pressure_msl_hpa')
    op.drop_column('weather_observations', 'apparent_temperature_c')
    op.drop_column('weather_observations', 'dew_point_c')
    op.drop_column('weather_observations', 'relative_humidity_pct')
    op.drop_column('weather_observations', 'precipitation_probability_pct')
    op.drop_column('weather_observations', 'showers_mm')
    op.drop_column('weather_observations', 'rain_mm')
    op.drop_column('weather_observations', 'precipitation_mm')
    op.drop_column('weather_observations', 'issue_time')
    op.drop_column('weather_observations', 'data_type')
    op.drop_column('weather_observations', 'longitude')
    op.drop_column('weather_observations', 'latitude')
