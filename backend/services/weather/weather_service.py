"""Domain service coordinating weather sampling, persistence, forecast horizons, and ML feature contracts."""

from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any
import uuid

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_MakeEnvelope, ST_MakePoint, ST_SetSRID, ST_X, ST_Y
from geoalchemy2.shape import to_shape
import redis.asyncio as aioredis
from shapely.wkt import loads as wkt_loads
from sqlalchemy import case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.observations import WeatherObservation
from backend.models.roads import RoadSegment
from backend.schemas.weather import (
    DailyForecastSummary,
    HourlyForecastItem,
    WeatherConditionFeatures,
    WeatherForecastResponse,
    WeatherMLFeatureVector,
    WeatherObservationResponse,
    WeatherRefreshResponse,
    WeatherStatusResponse,
)
from backend.services.events import EventPublisher, record_audit_log
from backend.services.weather.base import WeatherProvider
from backend.services.weather.open_meteo import OpenMeteoWeatherProvider

logger = logging.getLogger(__name__)
settings = get_settings()

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

STANDARD_WEATHER_UNITS = {
    "temperature": "°C",
    "apparent_temperature": "°C",
    "relative_humidity": "%",
    "dew_point": "°C",
    "precipitation": "mm",
    "rain": "mm",
    "showers": "mm",
    "snowfall": "cm",
    "precipitation_probability": "%",
    "wind_speed": "km/h",
    "wind_direction": "degrees",
    "wind_gusts": "km/h",
    "visibility": "m",
    "pressure_msl": "hPa",
    "surface_pressure": "hPa",
    "cloud_cover": "%",
    "soil_moisture": "m³/m³",
    "et0_evapotranspiration": "mm",
}


def extract_point_coordinates(geom_val: object) -> tuple[float, float]:
    """Safely extracts (lat, lon) float tuple from PostGIS geometry point."""
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
    """Manages weather ingestion, forecast persistence, freshness tracking, and ML feature vector derivation."""

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
        """Returns representative geographic sampling points strictly respecting corridor bounds."""
        min_lat, min_lon, max_lat, max_lon = settings.corridor_bbox
        valid_points = []
        for wp in CORRIDOR_WAYPOINTS:
            if min_lat <= wp["lat"] <= max_lat and min_lon <= wp["lon"] <= max_lon:
                valid_points.append(wp)

        if not valid_points:
            valid_points.append({
                "name": "Corridor Center",
                "lat": (min_lat + max_lat) / 2.0,
                "lon": (min_lon + max_lon) / 2.0,
            })

        return valid_points

    async def refresh_corridor_weather(
        self,
        actor_id: uuid.UUID | None = None,
        forecast_days: int = 2,
    ) -> WeatherRefreshResponse:
        """
        Fetches fresh observations and forecasts across corridor sampling waypoints.
        Persists current conditions and hourly forecast records idempotently.
        """
        start_time = time.time()
        sample_points = self.get_corridor_sample_points()
        current_persisted = 0
        forecast_persisted = 0
        last_error = None
        road_seg_cache: dict[tuple[float, float], str | None] = {}

        for pt in sample_points:
            lat = pt["lat"]
            lon = pt["lon"]
            try:
                # Use fetch_weather if available; fall back to fetch_current_observation
                if hasattr(self.provider, "fetch_weather"):
                    weather_pack = await self.provider.fetch_weather(lat, lon, forecast_days=forecast_days)
                    current_obs = weather_pack.get("current")
                    hourly_list = weather_pack.get("hourly") or []
                    daily_list = weather_pack.get("daily") or []
                else:
                    current_obs = await self.provider.fetch_current_observation(lat, lon)
                    hourly_list = []
                    daily_list = []

                # 1. Persist current condition
                if current_obs:
                    saved_curr = await self._persist_observation_if_new(
                        obs_data=current_obs,
                        lat=lat,
                        lon=lon,
                        road_seg_cache=road_seg_cache,
                    )
                    if saved_curr:
                        current_persisted += 1

                # 2. Persist hourly forecasts / historical observations
                for hr_rec in hourly_list:
                    # Enforce raw payload reference for provenance
                    if "raw_payload" not in hr_rec:
                        hr_rec["raw_payload"] = {"daily_summaries": daily_list}
                    saved_hr = await self._persist_observation_if_new(
                        obs_data=hr_rec,
                        lat=lat,
                        lon=lon,
                        road_seg_cache=road_seg_cache,
                    )
                    if saved_hr and hr_rec.get("data_type") == "FORECAST":
                        forecast_persisted += 1

            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"Weather fetch failed for '{pt['name']}' ({lat}, {lon}): {exc}")

        duration = time.time() - start_time
        now = datetime.now(timezone.utc)
        total_persisted = current_persisted + forecast_persisted

        # Cache last run status in Redis
        status_key = f"weather:{self.provider.name}:status"
        try:
            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
            status_data = {
                "last_run_status": "SUCCESS" if total_persisted > 0 or not last_error else "PARTIAL_FAILURE",
                "last_run_timestamp": now.isoformat(),
                "last_error": last_error,
                "persisted_count": total_persisted,
                "current_persisted": current_persisted,
                "forecast_persisted": forecast_persisted,
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
                "persisted_count": total_persisted,
                "current_persisted": current_persisted,
                "forecast_persisted": forecast_persisted,
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
                "total_persisted": total_persisted,
                "current_persisted": current_persisted,
                "forecast_persisted": forecast_persisted,
                "refreshed_at": now.isoformat(),
            },
        )

        return WeatherRefreshResponse(
            provider=self.provider.name,
            sample_points_queried=len(sample_points),
            observations_persisted=total_persisted,
            current_observations_persisted=current_persisted,
            forecast_records_persisted=forecast_persisted,
            duration_seconds=round(duration, 3),
            refreshed_at=now,
        )

    async def _persist_observation_if_new(
        self,
        obs_data: dict[str, Any],
        lat: float,
        lon: float,
        road_seg_cache: dict[tuple[float, float], str | None] | None = None,
    ) -> bool:
        """
        Deduplicates against existing records for provider, data_type, target timestamp, and coordinates.
        Associates to nearest road segment if available.
        """
        observed_at = obs_data.get("observed_at") or datetime.now(timezone.utc)
        forecast_valid_at = obs_data.get("forecast_valid_at") or observed_at
        data_type = obs_data.get("data_type", "CURRENT")
        r_lat = round(lat, 4)
        r_lon = round(lon, 4)

        # Deduplication and Upsert: check if record already exists for provider, data_type, valid_time, coords
        existing_query = select(WeatherObservation).where(
            WeatherObservation.provider == self.provider.name,
            WeatherObservation.data_type == data_type,
            WeatherObservation.forecast_valid_at == forecast_valid_at,
            WeatherObservation.latitude == r_lat,
            WeatherObservation.longitude == r_lon,
        ).limit(1)

        existing = await self.session.execute(existing_query)
        existing_obs = existing.scalar_one_or_none()
        if existing_obs:
            # Upsert / update existing record with refreshed values to avoid stale data
            existing_obs.temperature_c = obs_data.get("temperature_c")
            existing_obs.rainfall_mm = obs_data.get("rainfall_mm")
            existing_obs.precipitation_mm = obs_data.get("precipitation_mm", obs_data.get("rainfall_mm"))
            existing_obs.rain_mm = obs_data.get("rain_mm")
            existing_obs.showers_mm = obs_data.get("showers_mm")
            existing_obs.snowfall_cm = obs_data.get("snowfall_cm")
            existing_obs.precipitation_probability_pct = obs_data.get("precipitation_probability_pct")
            existing_obs.relative_humidity_pct = obs_data.get("relative_humidity_pct")
            existing_obs.dew_point_c = obs_data.get("dew_point_c")
            existing_obs.apparent_temperature_c = obs_data.get("apparent_temperature_c")
            existing_obs.pressure_msl_hpa = obs_data.get("pressure_msl_hpa")
            existing_obs.surface_pressure_hpa = obs_data.get("surface_pressure_hpa")
            existing_obs.wind_speed_kmh = obs_data.get("wind_speed_kmh")
            existing_obs.wind_direction_deg = obs_data.get("wind_direction_deg")
            existing_obs.wind_gusts_kmh = obs_data.get("wind_gusts_kmh")
            existing_obs.visibility_m = obs_data.get("visibility_m")
            existing_obs.weather_code = obs_data.get("weather_code")
            existing_obs.cloud_cover_pct = obs_data.get("cloud_cover_pct")
            existing_obs.et0_evapotranspiration_mm = obs_data.get("et0_evapotranspiration_mm")
            existing_obs.soil_moisture_m3m3 = obs_data.get("soil_moisture_m3m3")
            if "issue_time" in obs_data:
                existing_obs.issue_time = obs_data.get("issue_time")
            existing_obs.observed_at = observed_at
            existing_obs.ingested_at = datetime.now(timezone.utc)
            if "raw_payload" in obs_data:
                existing_obs.raw_payload = obs_data.get("raw_payload")
            if existing_obs.road_segment_id is None and road_seg_cache is not None and (r_lat, r_lon) in road_seg_cache:
                existing_obs.road_segment_id = road_seg_cache[(r_lat, r_lon)]
            return False

        # Attempt associating to nearest road segment using cache to avoid repeated GIS queries
        pt_geom = ST_SetSRID(ST_MakePoint(r_lon, r_lat), 4326)
        road_seg_id = None
        if road_seg_cache is not None and (r_lat, r_lon) in road_seg_cache:
            road_seg_id = road_seg_cache[(r_lat, r_lon)]
        else:
            nearest_seg_query = (
                select(RoadSegment.id)
                .order_by(func.ST_Distance(cast(RoadSegment.geom, Geography), cast(pt_geom, Geography)))
                .limit(1)
            )
            nearest_seg_res = await self.session.execute(nearest_seg_query)
            road_seg_id = nearest_seg_res.scalar_one_or_none()
            if road_seg_cache is not None:
                road_seg_cache[(r_lat, r_lon)] = road_seg_id

        obs = WeatherObservation(
            id=uuid.uuid4(),
            provider=self.provider.name,
            data_type=data_type,
            latitude=r_lat,
            longitude=r_lon,
            location_geom=pt_geom,
            road_segment_id=road_seg_id,
            temperature_c=obs_data.get("temperature_c"),
            rainfall_mm=obs_data.get("rainfall_mm"),
            precipitation_mm=obs_data.get("precipitation_mm", obs_data.get("rainfall_mm")),
            rain_mm=obs_data.get("rain_mm"),
            showers_mm=obs_data.get("showers_mm"),
            snowfall_cm=obs_data.get("snowfall_cm"),
            precipitation_probability_pct=obs_data.get("precipitation_probability_pct"),
            relative_humidity_pct=obs_data.get("relative_humidity_pct"),
            dew_point_c=obs_data.get("dew_point_c"),
            apparent_temperature_c=obs_data.get("apparent_temperature_c"),
            pressure_msl_hpa=obs_data.get("pressure_msl_hpa"),
            surface_pressure_hpa=obs_data.get("surface_pressure_hpa"),
            wind_speed_kmh=obs_data.get("wind_speed_kmh"),
            wind_direction_deg=obs_data.get("wind_direction_deg"),
            wind_gusts_kmh=obs_data.get("wind_gusts_kmh"),
            visibility_m=obs_data.get("visibility_m"),
            weather_code=obs_data.get("weather_code"),
            cloud_cover_pct=obs_data.get("cloud_cover_pct"),
            et0_evapotranspiration_mm=obs_data.get("et0_evapotranspiration_mm"),
            soil_moisture_m3m3=obs_data.get("soil_moisture_m3m3"),
            observed_at=observed_at,
            forecast_valid_at=forecast_valid_at,
            issue_time=obs_data.get("issue_time"),
            ingested_at=datetime.now(timezone.utc),
            raw_payload=obs_data.get("raw_payload"),
        )
        self.session.add(obs)
        return True

    async def get_latest_observations(
        self,
        limit: int = 50,
        data_type: str | None = None,
        road_segment_id: str | None = None,
        min_lat: float | None = None,
        min_lon: float | None = None,
        max_lat: float | None = None,
        max_lon: float | None = None,
    ) -> list[WeatherObservationResponse]:
        """Retrieves recent weather readings with spatial and data-type filtering."""
        query = select(WeatherObservation)

        if data_type:
            query = query.where(WeatherObservation.data_type == data_type)
        if road_segment_id:
            query = query.where(WeatherObservation.road_segment_id == road_segment_id)

        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = query.where(func.ST_Intersects(WeatherObservation.location_geom, bbox_geom))

        res = await self.session.execute(
            query.order_by(WeatherObservation.observed_at.desc(), WeatherObservation.forecast_valid_at.desc()).limit(limit)
        )
        observations = res.scalars().all()

        results = []
        for obs in observations:
            lat = obs.latitude
            lon = obs.longitude
            if lat is None or lon is None:
                lat, lon = extract_point_coordinates(obs.location_geom)

            results.append(
                WeatherObservationResponse(
                    id=obs.id,
                    provider=obs.provider,
                    data_type=obs.data_type,
                    latitude=lat,
                    longitude=lon,
                    rainfall_mm=obs.rainfall_mm,
                    precipitation_mm=obs.precipitation_mm,
                    rain_mm=obs.rain_mm,
                    showers_mm=obs.showers_mm,
                    precipitation_probability_pct=obs.precipitation_probability_pct,
                    relative_humidity_pct=obs.relative_humidity_pct,
                    dew_point_c=obs.dew_point_c,
                    apparent_temperature_c=obs.apparent_temperature_c,
                    pressure_msl_hpa=obs.pressure_msl_hpa,
                    surface_pressure_hpa=obs.surface_pressure_hpa,
                    wind_speed_kmh=obs.wind_speed_kmh,
                    wind_direction_deg=obs.wind_direction_deg,
                    wind_gusts_kmh=obs.wind_gusts_kmh,
                    snowfall_cm=obs.snowfall_cm,
                    weather_code=obs.weather_code,
                    visibility_m=obs.visibility_m,
                    temperature_c=obs.temperature_c,
                    cloud_cover_pct=obs.cloud_cover_pct,
                    et0_evapotranspiration_mm=obs.et0_evapotranspiration_mm,
                    soil_moisture_m3m3=obs.soil_moisture_m3m3,
                    road_segment_id=obs.road_segment_id,
                    observed_at=obs.observed_at,
                    forecast_valid_at=obs.forecast_valid_at,
                    issue_time=obs.issue_time,
                    ingested_at=obs.ingested_at,
                )
            )
        return results

    async def get_forecast(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        road_segment_id: str | None = None,
        hours: int = 24,
    ) -> WeatherForecastResponse:
        """
        Retrieves hourly forecast prediction series and daily summaries for a requested coordinate
        or road segment.
        """
        hours = max(1, min(hours, 72))
        now = datetime.now(timezone.utc)

        # 1. Resolve coordinates
        target_lat = latitude
        target_lon = longitude
        if road_segment_id and (target_lat is None or target_lon is None):
            seg_query = select(RoadSegment).where(RoadSegment.id == road_segment_id)
            seg_res = await self.session.execute(seg_query)
            seg = seg_res.scalar_one_or_none()
            if seg and seg.geom is not None:
                shape = to_shape(seg.geom)
                centroid = shape.centroid
                target_lat = float(centroid.y)
                target_lon = float(centroid.x)

        if target_lat is None or target_lon is None:
            # Default to first corridor waypoint (Guwahati)
            pts = self.get_corridor_sample_points()
            target_lat = pts[0]["lat"]
            target_lon = pts[0]["lon"]

        pt_geom = ST_SetSRID(ST_MakePoint(round(target_lon, 4), round(target_lat, 4)), 4326)

        # 2. Find nearest weather sampling point in DB with forecast records
        nearest_query = (
            select(WeatherObservation.latitude, WeatherObservation.longitude)
            .where(WeatherObservation.data_type == "FORECAST")
            .order_by(func.ST_Distance(cast(WeatherObservation.location_geom, Geography), cast(pt_geom, Geography)))
            .limit(1)
        )
        near_res = await self.session.execute(nearest_query)
        station_coord = near_res.first()

        if station_coord:
            station_lat, station_lon = station_coord
        else:
            station_lat, station_lon = target_lat, target_lon

        # 3. Retrieve forecast records for the station, deduplicating across runs with row_number
        rn_col = func.row_number().over(
            partition_by=WeatherObservation.forecast_valid_at,
            order_by=[
                WeatherObservation.issue_time.desc().nulls_last(),
                WeatherObservation.ingested_at.desc().nulls_last(),
                WeatherObservation.observed_at.desc().nulls_last(),
            ],
        ).label("rn")

        subq = (
            select(
                WeatherObservation.id.label("obs_id"),
                WeatherObservation.forecast_valid_at.label("valid_at"),
                rn_col,
            )
            .where(
                WeatherObservation.data_type == "FORECAST",
                WeatherObservation.latitude == station_lat,
                WeatherObservation.longitude == station_lon,
                WeatherObservation.forecast_valid_at >= now - timedelta(hours=1),
            )
            .subquery()
        )

        fc_query = (
            select(WeatherObservation)
            .join(subq, WeatherObservation.id == subq.c.obs_id)
            .where(subq.c.rn == 1)
            .order_by(WeatherObservation.forecast_valid_at.asc())
            .limit(hours)
        )
        fc_res = await self.session.execute(fc_query)
        fc_records = fc_res.scalars().all()

        hourly_items = []
        daily_summaries = []

        for rec in fc_records:
            hourly_items.append(
                HourlyForecastItem(
                    valid_time=rec.forecast_valid_at or rec.observed_at,
                    temperature_c=rec.temperature_c,
                    apparent_temperature_c=rec.apparent_temperature_c,
                    precipitation_mm=rec.precipitation_mm,
                    rain_mm=rec.rain_mm,
                    showers_mm=rec.showers_mm,
                    snowfall_cm=rec.snowfall_cm,
                    precipitation_probability_pct=rec.precipitation_probability_pct,
                    relative_humidity_pct=rec.relative_humidity_pct,
                    dew_point_c=rec.dew_point_c,
                    pressure_msl_hpa=rec.pressure_msl_hpa,
                    surface_pressure_hpa=rec.surface_pressure_hpa,
                    wind_speed_kmh=rec.wind_speed_kmh,
                    wind_direction_deg=rec.wind_direction_deg,
                    wind_gusts_kmh=rec.wind_gusts_kmh,
                    visibility_m=rec.visibility_m,
                    weather_code=rec.weather_code,
                    cloud_cover_pct=rec.cloud_cover_pct,
                    soil_moisture_m3m3=rec.soil_moisture_m3m3,
                    et0_evapotranspiration_mm=rec.et0_evapotranspiration_mm,
                )
            )

        # Extract daily summaries if stored in raw_payload of recent records
        if fc_records and fc_records[0].raw_payload:
            raw_dailies = fc_records[0].raw_payload.get("daily_summaries") or []
            for d in raw_dailies:
                try:
                    daily_summaries.append(DailyForecastSummary(**d))
                except Exception:
                    pass

        return WeatherForecastResponse(
            provider=self.provider.name,
            latitude=station_lat,
            longitude=station_lon,
            road_segment_id=road_segment_id,
            generated_at=now,
            horizon_hours=len(hourly_items),
            hourly=hourly_items,
            daily=daily_summaries,
        )

    async def get_weather_features_for_ml(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        road_segment_id: str | None = None,
        reference_time: datetime | None = None,
    ) -> WeatherMLFeatureVector:
        """
        Constructs a downstream ML-ready feature vector for a requested location or road segment.
        Derives rolling past rainfall accumulation (1h, 3h, 6h, 24h) and future forecast accumulation (1h, 3h, 6h, 24h)
        with interval semantics and explicit data completeness indicators.
        """
        now = datetime.now(timezone.utc)
        target_lat = latitude
        target_lon = longitude
        road_dist_m = None
        confidence = "UNMATCHED"

        # 1. Resolve coordinates from road segment if requested
        if road_segment_id and (target_lat is None or target_lon is None):
            seg_query = select(RoadSegment).where(RoadSegment.id == road_segment_id)
            seg_res = await self.session.execute(seg_query)
            seg = seg_res.scalar_one_or_none()
            if seg and seg.geom is not None:
                shape = to_shape(seg.geom)
                centroid = shape.centroid
                target_lat = float(centroid.y)
                target_lon = float(centroid.x)

        if target_lat is None or target_lon is None:
            pts = self.get_corridor_sample_points()
            target_lat = pts[0]["lat"]
            target_lon = pts[0]["lon"]

        pt_geom = ST_SetSRID(ST_MakePoint(round(target_lon, 4), round(target_lat, 4)), 4326)

        # 2. Find nearest weather station and compute distance
        station_query = (
            select(
                WeatherObservation.latitude,
                WeatherObservation.longitude,
                func.ST_Distance(cast(WeatherObservation.location_geom, Geography), cast(pt_geom, Geography)),
            )
            .order_by(func.ST_Distance(cast(WeatherObservation.location_geom, Geography), cast(pt_geom, Geography)))
            .limit(1)
        )
        station_res = await self.session.execute(station_query)
        station_row = station_res.first()

        if station_row:
            station_lat, station_lon, dist_m = station_row
            road_dist_m = round(float(dist_m), 1) if dist_m is not None else 0.0
            if road_dist_m <= 2000.0:
                confidence = "HIGH"
            elif road_dist_m <= 10000.0:
                confidence = "MEDIUM"
            elif road_dist_m <= 30000.0:
                confidence = "LOW"
            else:
                confidence = "UNMATCHED"
        else:
            station_lat, station_lon = target_lat, target_lon
            confidence = "HIGH"
            road_dist_m = 0.0

        # 3. Retrieve most recent observation at or before reference time
        ref_time = reference_time or now
        curr_query = (
            select(WeatherObservation)
            .where(
                WeatherObservation.latitude == station_lat,
                WeatherObservation.longitude == station_lon,
                WeatherObservation.data_type.in_(["CURRENT", "OBSERVATION"]),
                WeatherObservation.observed_at <= ref_time,
            )
            .order_by(
                (WeatherObservation.data_type == "CURRENT").desc(),
                WeatherObservation.observed_at.desc(),
            )
            .limit(1)
        )
        curr_res = await self.session.execute(curr_query)
        curr_obs = curr_res.scalar_one_or_none()

        if curr_obs and reference_time is None:
            ref_time = curr_obs.observed_at
        data_freshness_seconds = None
        is_stale = True
        stale_limit_sec = getattr(settings, "WEATHER_STALE_THRESHOLD_MINUTES", 120) * 60

        missing_indicators: list[str] = []

        if curr_obs:
            diff_sec = (now - curr_obs.observed_at).total_seconds()
            data_freshness_seconds = max(0.0, round(diff_sec, 1))
            is_stale = data_freshness_seconds > stale_limit_sec

            current_features = WeatherConditionFeatures(
                temperature_c=curr_obs.temperature_c,
                apparent_temperature_c=curr_obs.apparent_temperature_c,
                relative_humidity_pct=curr_obs.relative_humidity_pct,
                dew_point_c=curr_obs.dew_point_c,
                precipitation_mm=curr_obs.precipitation_mm,
                rainfall_mm=curr_obs.rainfall_mm,
                wind_speed_kmh=curr_obs.wind_speed_kmh,
                wind_gusts_kmh=curr_obs.wind_gusts_kmh,
                wind_direction_deg=curr_obs.wind_direction_deg,
                visibility_m=curr_obs.visibility_m,
                pressure_msl_hpa=curr_obs.pressure_msl_hpa,
                surface_pressure_hpa=curr_obs.surface_pressure_hpa,
                weather_code=curr_obs.weather_code,
                cloud_cover_pct=curr_obs.cloud_cover_pct,
                soil_moisture_m3m3=curr_obs.soil_moisture_m3m3,
                et0_evapotranspiration_mm=curr_obs.et0_evapotranspiration_mm,
            )

            # Record missing indicators
            for field_name in WeatherConditionFeatures.model_fields:
                if getattr(current_features, field_name) is None:
                    missing_indicators.append(field_name)
        else:
            current_features = WeatherConditionFeatures()
            missing_indicators = list(WeatherConditionFeatures.model_fields.keys())

        # 4. Derive rolling precipitation accumulation over past windows: 1h, 3h, 6h, 24h
        past_accum: dict[str, float | None] = {}
        past_completeness: dict[str, str] = {}
        precip_expr = func.coalesce(WeatherObservation.precipitation_mm, WeatherObservation.rainfall_mm)

        for w_hours in [1, 3, 6, 24]:
            w_start = ref_time - timedelta(hours=w_hours)

            # Prioritize OBSERVATION/CURRENT over FORECAST, then latest issue_time/ingested_at/observed_at
            priority_expr = case(
                (WeatherObservation.data_type.in_(["CURRENT", "OBSERVATION"]), 0),
                else_=1,
            )
            rn_col = func.row_number().over(
                partition_by=WeatherObservation.forecast_valid_at,
                order_by=[
                    priority_expr.asc(),
                    WeatherObservation.issue_time.desc().nulls_last(),
                    WeatherObservation.ingested_at.desc().nulls_last(),
                    WeatherObservation.observed_at.desc().nulls_last(),
                ],
            ).label("rn")

            subq = (
                select(
                    WeatherObservation.forecast_valid_at.label("valid_at"),
                    precip_expr.label("precip_val"),
                    rn_col,
                )
                .where(
                    WeatherObservation.latitude == station_lat,
                    WeatherObservation.longitude == station_lon,
                    WeatherObservation.forecast_valid_at > w_start,
                    WeatherObservation.forecast_valid_at <= ref_time,
                    precip_expr.isnot(None),
                )
                .subquery()
            )

            past_query = (
                select(subq.c.valid_at, subq.c.precip_val)
                .where(subq.c.rn == 1)
                .order_by(subq.c.valid_at.asc())
            )
            p_res = await self.session.execute(past_query)
            distinct_intervals = p_res.all()

            valid_vals = [float(r[1]) for r in distinct_intervals if r[1] is not None]

            if len(valid_vals) >= w_hours:
                past_accum[f"past_{w_hours}h_mm"] = round(sum(valid_vals[:w_hours]), 2)
                past_completeness[f"past_{w_hours}h"] = "COMPLETE"
            elif len(valid_vals) > 0 and len(valid_vals) >= max(1, int(w_hours * 0.7)):
                past_accum[f"past_{w_hours}h_mm"] = round(sum(valid_vals), 2)
                past_completeness[f"past_{w_hours}h"] = "PARTIAL"
            else:
                # Do NOT silently convert missing interval to zero!
                past_accum[f"past_{w_hours}h_mm"] = None
                past_completeness[f"past_{w_hours}h"] = "INSUFFICIENT_DATA"

        # 5. Derive forecast rainfall accumulation over future windows: 1h, 3h, 6h, 24h
        forecast_accum: dict[str, float | None] = {}
        forecast_completeness: dict[str, str] = {}

        for w_hours in [1, 3, 6, 24]:
            w_end = ref_time + timedelta(hours=w_hours)

            rn_col = func.row_number().over(
                partition_by=WeatherObservation.forecast_valid_at,
                order_by=[
                    WeatherObservation.issue_time.desc().nulls_last(),
                    WeatherObservation.ingested_at.desc().nulls_last(),
                    WeatherObservation.observed_at.desc().nulls_last(),
                ],
            ).label("rn")

            subq = (
                select(
                    WeatherObservation.forecast_valid_at.label("valid_at"),
                    precip_expr.label("precip_val"),
                    rn_col,
                )
                .where(
                    WeatherObservation.latitude == station_lat,
                    WeatherObservation.longitude == station_lon,
                    WeatherObservation.data_type == "FORECAST",
                    WeatherObservation.forecast_valid_at > ref_time,
                    WeatherObservation.forecast_valid_at <= w_end,
                    precip_expr.isnot(None),
                )
                .subquery()
            )

            fc_query = (
                select(subq.c.valid_at, subq.c.precip_val)
                .where(subq.c.rn == 1)
                .order_by(subq.c.valid_at.asc())
            )
            fc_res = await self.session.execute(fc_query)
            distinct_fc_intervals = fc_res.all()

            fc_vals = [float(r[1]) for r in distinct_fc_intervals if r[1] is not None]

            if len(fc_vals) >= w_hours:
                forecast_accum[f"next_{w_hours}h_mm"] = round(sum(fc_vals[:w_hours]), 2)
                forecast_completeness[f"next_{w_hours}h"] = "COMPLETE"
            elif len(fc_vals) > 0 and len(fc_vals) >= max(1, int(w_hours * 0.7)):
                forecast_accum[f"next_{w_hours}h_mm"] = round(sum(fc_vals), 2)
                forecast_completeness[f"next_{w_hours}h"] = "PARTIAL"
            else:
                forecast_accum[f"next_{w_hours}h_mm"] = None
                forecast_completeness[f"next_{w_hours}h"] = "INSUFFICIENT_DATA"

        return WeatherMLFeatureVector(
            schema_version="1.0",
            provider=self.provider.name,
            latitude=station_lat,
            longitude=station_lon,
            road_segment_id=road_segment_id,
            road_segment_distance_m=road_dist_m,
            spatial_match_confidence=confidence,
            reference_time=ref_time,
            issue_time=curr_obs.issue_time if curr_obs else None,
            data_freshness_seconds=data_freshness_seconds,
            is_stale=is_stale,
            current_conditions=current_features,
            rainfall_accumulation_past=past_accum,
            past_data_completeness=past_completeness,
            rainfall_forecast_accumulation=forecast_accum,
            forecast_data_completeness=forecast_completeness,
            units=STANDARD_WEATHER_UNITS,
            missing_indicators=missing_indicators,
        )

    async def get_status(self) -> WeatherStatusResponse:
        """Inspects operational metrics, freshness, and last execution status."""
        count_res = await self.session.execute(select(func.count(WeatherObservation.id)))
        total_obs = count_res.scalar() or 0

        curr_count_res = await self.session.execute(
            select(func.count(WeatherObservation.id)).where(WeatherObservation.data_type.in_(["CURRENT", "OBSERVATION"]))
        )
        total_curr = curr_count_res.scalar() or 0

        fc_count_res = await self.session.execute(
            select(func.count(WeatherObservation.id)).where(WeatherObservation.data_type == "FORECAST")
        )
        total_fc = fc_count_res.scalar() or 0

        latest_obs_res = await self.session.execute(
            select(WeatherObservation.observed_at)
            .where(WeatherObservation.data_type.in_(["CURRENT", "OBSERVATION"]))
            .order_by(WeatherObservation.observed_at.desc())
            .limit(1)
        )
        latest_time = latest_obs_res.scalar_one_or_none()

        sample_points = self.get_corridor_sample_points()
        now = datetime.now(timezone.utc)
        refresh_interval = settings.WEATHER_REFRESH_INTERVAL_MINUTES
        is_stale = True
        if latest_time:
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
            total_current_observations=total_curr,
            total_forecast_records=total_fc,
            corridor_sample_points_count=len(sample_points),
            latest_observation_time=latest_time,
            is_stale=is_stale,
            refresh_interval_minutes=refresh_interval,
        )
