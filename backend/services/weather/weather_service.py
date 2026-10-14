"""Domain service coordinating weather sampling, persistence, and freshness tracking."""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_MakeEnvelope, ST_MakePoint, ST_SetSRID
from geoalchemy2.shape import to_shape
from shapely.wkt import loads as wkt_loads
from sqlalchemy import cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from backend.config import get_settings
from backend.models.observations import WeatherObservation
from backend.models.roads import RoadSegment
from backend.schemas.weather import (
    WeatherObservationResponse,
    WeatherRefreshResponse,
    WeatherStatusResponse,
)
from backend.services.events import EventPublisher, record_audit_log
from backend.services.weather.base import WeatherProvider
from backend.services.weather.open_meteo import OpenMeteoWeatherProvider

logger = logging.getLogger(__name__)
settings = get_settings()

# Representative key corridor locations for geographic sampling
CORRIDOR_WAYPOINTS: list[dict[str, Any]] = [
    {"name": "Guwahati Hub", "lat": 26.1445, "lon": 91.7362},
    {"name": "Rangia Junction", "lat": 26.4350, "lon": 91.6210},
    {"name": "Tezpur Foothills", "lat": 26.6500, "lon": 92.7900},
    {"name": "Balipara Entry", "lat": 26.8330, "lon": 92.7820},
    {"name": "Bhalukpong Gate", "lat": 27.0120, "lon": 92.6450},
    {"name": "Bomdila Pass", "lat": 27.2645, "lon": 92.4159},
    {"name": "Dirang Valley", "lat": 27.3580, "lon": 92.2350},
    {"name": "Sela High Ridge", "lat": 27.5040, "lon": 92.1020},
    {"name": "Tawang Depot", "lat": 27.5860, "lon": 91.8590},
]


def extract_point_coordinates(geom_val: object) -> tuple[float, float]:
    if geom_val is None:
        return (0.0, 0.0)
    try:
        shape = to_shape(geom_val)
        return float(shape.y), float(shape.x)
    except Exception:
        s = str(geom_val)
        if "POINT" in s:
            wkt_part = s.split(";")[-1]
            shape = wkt_loads(wkt_part)
            return float(shape.y), float(shape.x)
        return (0.0, 0.0)


class WeatherService:
    """Manages weather ingestion, corridor spatial sampling, and freshness monitoring."""

    def __init__(
        self,
        session: AsyncSession,
        provider: WeatherProvider | None = None,
        event_publisher: EventPublisher | None = None,
    ):
        self.session = session
        self.provider = provider or OpenMeteoWeatherProvider()
        self.publisher = event_publisher or EventPublisher()

    def get_corridor_sample_points(self) -> list[dict[str, Any]]:
        """
        Returns representative geographic sampling points strictly respecting corridor bounds.
        """
        min_lat, min_lon, max_lat, max_lon = settings.corridor_bbox
        valid_points = []
        for wp in CORRIDOR_WAYPOINTS:
            if min_lat <= wp["lat"] <= max_lat and min_lon <= wp["lon"] <= max_lon:
                valid_points.append(wp)

        # Fallback to bbox midpoint if no waypoints fell inside custom bounds
        if not valid_points:
            valid_points.append({
                "name": "Corridor Center",
                "lat": (min_lat + max_lat) / 2.0,
                "lon": (min_lon + max_lon) / 2.0,
            })

        return valid_points

    async def refresh_corridor_weather(self, actor_id: uuid.UUID | None = None) -> WeatherRefreshResponse:
        """
        Fetches fresh observations for corridor sampling points from the provider
        and persists non-duplicate observations.
        """
        start_time = time.time()
        sample_points = self.get_corridor_sample_points()
        persisted_count = 0
        last_error = None

        for pt in sample_points:
            lat = pt["lat"]
            lon = pt["lon"]
            try:
                obs_data = await self.provider.fetch_current_observation(lat, lon)
                saved = await self._persist_observation_if_new(obs_data, lat, lon)
                if saved:
                    persisted_count += 1
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"Weather fetch failed for '{pt['name']}' ({lat}, {lon}): {exc}")

        duration = time.time() - start_time
        now = datetime.now(timezone.utc)

        # Cache last run status in Redis
        status_key = f"weather:{self.provider.name}:status"
        try:
            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
            status_data = {
                "last_run_status": "SUCCESS" if persisted_count > 0 or not last_error else "PARTIAL_FAILURE",
                "last_run_timestamp": now.isoformat(),
                "last_error": last_error,
                "persisted_count": persisted_count,
            }
            await client.set(status_key, json.dumps(status_data), ex=86400)
            await client.aclose()
        except Exception as exc:
            logger.debug(f"Redis cache write skipped for weather status: {exc}")

        # Audit log
        record_audit_log(
            session=self.session,
            action="weather_refreshed",
            entity_type="weather_provider",
            entity_id=self.provider.name,
            actor_id=actor_id,
            details={
                "persisted_count": persisted_count,
                "sample_points_count": len(sample_points),
                "duration_s": duration,
                "last_error": last_error,
            },
        )
        await self.session.commit()

        # Publish event
        await self.publisher.publish_event(
            event_type="weather.updated",
            entity_id=self.provider.name,
            payload={
                "provider": self.provider.name,
                "persisted_count": persisted_count,
                "refreshed_at": now.isoformat(),
            },
        )

        return WeatherRefreshResponse(
            provider=self.provider.name,
            sample_points_queried=len(sample_points),
            observations_persisted=persisted_count,
            duration_seconds=round(duration, 3),
            refreshed_at=now,
        )

    async def _persist_observation_if_new(
        self,
        obs_data: dict[str, Any],
        lat: float,
        lon: float,
    ) -> bool:
        """
        Deduplicates against existing observations for the same provider, coordinates, and timestamp.
        Associates to nearest road segment if available.
        """
        observed_at = obs_data["observed_at"]
        pt_geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        # Deduplication query: check if observation for this provider, time, and location already exists
        existing_query = select(WeatherObservation.id).where(
            WeatherObservation.provider == self.provider.name,
            WeatherObservation.observed_at == observed_at,
            func.ST_DWithin(cast(WeatherObservation.location_geom, Geography), cast(pt_geom, Geography), 100.0),
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            return False

        # Attempt associating to nearest road segment
        nearest_seg_query = (
            select(RoadSegment.id)
            .order_by(func.ST_Distance(cast(RoadSegment.geom, Geography), cast(pt_geom, Geography)))
            .limit(1)
        )
        nearest_seg_res = await self.session.execute(nearest_seg_query)
        road_seg_id = nearest_seg_res.scalar_one_or_none()

        obs = WeatherObservation(
            id=uuid.uuid4(),
            provider=self.provider.name,
            location_geom=pt_geom,
            road_segment_id=road_seg_id,
            temperature_c=obs_data.get("temperature_c"),
            rainfall_mm=obs_data.get("rainfall_mm"),
            wind_speed_kmh=obs_data.get("wind_speed_kmh"),
            wind_gusts_kmh=obs_data.get("wind_gusts_kmh"),
            snowfall_cm=obs_data.get("snowfall_cm"),
            weather_code=obs_data.get("weather_code"),
            visibility_m=obs_data.get("visibility_m"),
            observed_at=observed_at,
            forecast_valid_at=obs_data.get("forecast_valid_at", observed_at),
            ingested_at=datetime.now(timezone.utc),
            raw_payload=obs_data.get("raw_payload"),
        )
        self.session.add(obs)
        return True

    async def get_latest_observations(
        self,
        limit: int = 50,
        min_lat: float | None = None,
        min_lon: float | None = None,
        max_lat: float | None = None,
        max_lon: float | None = None,
    ) -> list[WeatherObservationResponse]:
        """Retrieves recent weather readings with spatial filtering."""
        query = select(WeatherObservation)

        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = query.where(func.ST_Intersects(WeatherObservation.location_geom, bbox_geom))

        res = await self.session.execute(
            query.order_by(WeatherObservation.observed_at.desc()).limit(limit)
        )
        observations = res.scalars().all()

        results = []
        for obs in observations:
            lat, lon = extract_point_coordinates(obs.location_geom)
            results.append(
                WeatherObservationResponse(
                    id=obs.id,
                    provider=obs.provider,
                    latitude=lat,
                    longitude=lon,
                    rainfall_mm=obs.rainfall_mm,
                    wind_speed_kmh=obs.wind_speed_kmh,
                    wind_gusts_kmh=obs.wind_gusts_kmh,
                    snowfall_cm=obs.snowfall_cm,
                    weather_code=obs.weather_code,
                    visibility_m=obs.visibility_m,
                    temperature_c=obs.temperature_c,
                    road_segment_id=obs.road_segment_id,
                    observed_at=obs.observed_at,
                    forecast_valid_at=obs.forecast_valid_at,
                    ingested_at=obs.ingested_at,
                )
            )
        return results

    async def get_status(self) -> WeatherStatusResponse:
        """Inspects operational metrics, freshness, and last execution status."""
        count_res = await self.session.execute(select(func.count(WeatherObservation.id)))
        total_obs = count_res.scalar() or 0

        latest_obs_res = await self.session.execute(
            select(WeatherObservation.observed_at).order_by(WeatherObservation.observed_at.desc()).limit(1)
        )
        latest_time = latest_obs_res.scalar_one_or_none()

        sample_points = self.get_corridor_sample_points()
        now = datetime.now(timezone.utc)
        refresh_interval = settings.WEATHER_REFRESH_INTERVAL_MINUTES
        is_stale = True
        if latest_time:
            # Stale if older than 2 * refresh_interval
            is_stale = (now - latest_time) > timedelta(minutes=2 * refresh_interval)

        # Inspect Redis status if available
        last_error = None
        last_run_status = "UNKNOWN"
        try:
            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
            raw = await client.get(f"weather:{self.provider.name}:status")
            if raw:
                status_info = json.loads(raw)
                last_run_status = status_info.get("last_run_status", "SUCCESS")
                last_error = status_info.get("last_error")
            await client.aclose()
        except Exception:
            pass

        if last_run_status == "UNKNOWN" and total_obs > 0:
            last_run_status = "SUCCESS"

        return WeatherStatusResponse(
            provider=self.provider.name,
            last_run_status=last_run_status,
            last_successful_run=latest_time,
            last_error=last_error,
            total_observations=total_obs,
            corridor_sample_points_count=len(sample_points),
            latest_observation_time=latest_time,
            is_stale=is_stale,
            refresh_interval_minutes=refresh_interval,
        )
