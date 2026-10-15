"""Open-Meteo weather provider implementation.

Fetches current weather observations, hourly forecasts, and daily summaries
from the genuine Open-Meteo API with robust error handling, retries, and defensive parsing.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
import httpx

from backend.config import get_settings
from backend.services.weather.base import WeatherProvider

logger = logging.getLogger(__name__)
settings = get_settings()

CURRENT_VARIABLES = (
    "temperature_2m,"
    "relative_humidity_2m,"
    "apparent_temperature,"
    "precipitation,"
    "rain,"
    "showers,"
    "snowfall,"
    "weather_code,"
    "cloud_cover,"
    "pressure_msl,"
    "surface_pressure,"
    "wind_speed_10m,"
    "wind_direction_10m,"
    "wind_gusts_10m,"
    "visibility"
)

HOURLY_VARIABLES = (
    "temperature_2m,"
    "relative_humidity_2m,"
    "dew_point_2m,"
    "apparent_temperature,"
    "precipitation_probability,"
    "precipitation,"
    "rain,"
    "showers,"
    "snowfall,"
    "weather_code,"
    "pressure_msl,"
    "surface_pressure,"
    "cloud_cover,"
    "visibility,"
    "wind_speed_10m,"
    "wind_direction_10m,"
    "wind_gusts_10m,"
    "soil_moisture_0_to_7cm,"
    "et0_fao_evapotranspiration"
)

DAILY_VARIABLES = (
    "weather_code,"
    "temperature_2m_max,"
    "temperature_2m_min,"
    "apparent_temperature_max,"
    "apparent_temperature_min,"
    "sunrise,"
    "sunset,"
    "precipitation_sum,"
    "rain_sum,"
    "showers_sum,"
    "snowfall_sum,"
    "precipitation_probability_max,"
    "wind_speed_10m_max,"
    "wind_gusts_10m_max"
)


def parse_utc_timestamp(ts_val: str | None) -> datetime:
    """Safely normalizes an ISO timestamp string into UTC datetime."""
    if not ts_val:
        return datetime.now(timezone.utc)
    s = str(ts_val).strip()
    if not s.endswith("Z") and "+" not in s and "-" not in s[10:]:
        s += "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Genuine external meteorological feed using the Open-Meteo API.
    Supports temperature, precipitation, wind speed/gusts/direction, visibility,
    soil moisture, evapotranspiration, and WMO codes for both current readings and forecasts.
    """

    def __init__(
        self,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ):
        self.api_url = api_url or settings.OPEN_METEO_API_URL
        self.timeout = timeout_seconds or settings.WEATHER_REQUEST_TIMEOUT_SECONDS
        self.max_retries = max_retries or getattr(settings, "WEATHER_MAX_RETRIES", 3)

    @property
    def name(self) -> str:
        return "open-meteo"

    async def fetch_current_observation(self, lat: float, lon: float) -> dict[str, Any]:
        """Backward-compatible helper returning only the normalized current observation."""
        result = await self.fetch_weather(lat=lat, lon=lon, forecast_days=1)
        return result["current"]

    async def fetch_weather(
        self,
        lat: float,
        lon: float,
        forecast_days: int = 2,
    ) -> dict[str, Any]:
        """
        Fetches current conditions, hourly forecasts, and daily summaries
        from Open-Meteo with exponential backoff and retry handling.
        """
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "current": CURRENT_VARIABLES,
            "hourly": HOURLY_VARIABLES,
            "daily": DAILY_VARIABLES,
            "forecast_days": max(1, min(forecast_days, 7)),
            "timezone": "UTC",
        }

        last_error = None
        backoff_base = getattr(settings, "WEATHER_RETRY_BACKOFF_SECONDS", 0.5)

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(self.api_url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        return self._normalize_full_response(data, lat, lon)
                    elif resp.status_code == 429:
                        last_error = f"Open-Meteo rate limit (HTTP 429): {resp.text}"
                        logger.warning(f"Rate limited by Open-Meteo for ({lat}, {lon}) on attempt {attempt}")
                    elif resp.status_code >= 500:
                        last_error = f"Upstream HTTP {resp.status_code}: {resp.text}"
                        logger.warning(f"Upstream server error from Open-Meteo for ({lat}, {lon}): HTTP {resp.status_code}")
                    else:
                        resp.raise_for_status()
            except httpx.RequestError as exc:
                last_error = f"Network connection error: {exc}"
            except Exception as exc:
                last_error = str(exc)

            if attempt < self.max_retries:
                sleep_sec = backoff_base * (2 ** (attempt - 1))
                await asyncio.sleep(sleep_sec)

        raise RuntimeError(
            f"Open-Meteo request failed after {self.max_retries} attempts for ({lat}, {lon}): {last_error}"
        )

    def _normalize_full_response(
        self,
        data: dict[str, Any],
        req_lat: float,
        req_lon: float,
    ) -> dict[str, Any]:
        """
        Parses current, hourly, and daily sections into normalized dictionaries.
        Preserves None values without fabricating zeros.
        """
        now = datetime.now(timezone.utc)
        current_block = data.get("current")
        if not current_block:
            raise ValueError(f"Malformed Open-Meteo payload missing 'current' block: {data}")

        # Derive upstream issue / run time if available
        issue_time = parse_utc_timestamp(current_block.get("time")) if current_block.get("time") else now
        gen_time = data.get("generationtime_ms")

        # 1. Normalize Current Observation
        current_norm = self._normalize_current(current_block, req_lat, req_lon, data, issue_time)

        # 2. Normalize Hourly Forecasts (if present in response)
        hourly_list: list[dict[str, Any]] = []
        hourly_block = data.get("hourly")
        if hourly_block and isinstance(hourly_block, dict):
            hourly_list = self._normalize_hourly(hourly_block, req_lat, req_lon, issue_time, issue_time)

        # 3. Normalize Daily Summaries (if present in response)
        daily_list: list[dict[str, Any]] = []
        daily_block = data.get("daily")
        if daily_block and isinstance(daily_block, dict):
            daily_list = self._normalize_daily(daily_block)

        return {
            "current": current_norm,
            "hourly": hourly_list,
            "daily": daily_list,
            "metadata": {
                "provider": self.name,
                "latitude": req_lat,
                "longitude": req_lon,
                "elevation_m": data.get("elevation"),
                "generation_time_ms": gen_time,
                "issue_time": issue_time.isoformat(),
            },
        }

    def _normalize_current(
        self,
        current: dict[str, Any],
        req_lat: float,
        req_lon: float,
        raw_payload: dict[str, Any],
        issue_time: datetime,
    ) -> dict[str, Any]:
        """Extracts and normalizes current surface observations."""
        time_str = current.get("time")
        observed_at = parse_utc_timestamp(time_str)

        norm: dict[str, Any] = {
            "provider": self.name,
            "data_type": "CURRENT",
            "latitude": round(req_lat, 4),
            "longitude": round(req_lon, 4),
            "observed_at": observed_at,
            "forecast_valid_at": observed_at,
            "issue_time": issue_time,
            "raw_payload": raw_payload,
            "temperature_c": float(current["temperature_2m"]) if current.get("temperature_2m") is not None else None,
            "apparent_temperature_c": float(current["apparent_temperature"]) if current.get("apparent_temperature") is not None else None,
            "relative_humidity_pct": float(current["relative_humidity_2m"]) if current.get("relative_humidity_2m") is not None else None,
            "pressure_msl_hpa": float(current["pressure_msl"]) if current.get("pressure_msl") is not None else None,
            "surface_pressure_hpa": float(current["surface_pressure"]) if current.get("surface_pressure") is not None else None,
            "cloud_cover_pct": float(current["cloud_cover"]) if current.get("cloud_cover") is not None else None,
            "precipitation_mm": float(current["precipitation"]) if current.get("precipitation") is not None else None,
            "rain_mm": float(current["rain"]) if current.get("rain") is not None else None,
            "showers_mm": float(current["showers"]) if current.get("showers") is not None else None,
            "snowfall_cm": float(current["snowfall"]) if current.get("snowfall") is not None else None,
            "wind_speed_kmh": float(current["wind_speed_10m"]) if current.get("wind_speed_10m") is not None else None,
            "wind_direction_deg": float(current["wind_direction_10m"]) if current.get("wind_direction_10m") is not None else None,
            "wind_gusts_kmh": float(current["wind_gusts_10m"]) if current.get("wind_gusts_10m") is not None else None,
            "visibility_m": float(current["visibility"]) if current.get("visibility") is not None else None,
            "weather_code": int(current["weather_code"]) if current.get("weather_code") is not None else None,
        }

        # Backward-compatible rainfall_mm
        if norm["rain_mm"] is not None:
            norm["rainfall_mm"] = norm["rain_mm"]
        elif norm["precipitation_mm"] is not None:
            norm["rainfall_mm"] = norm["precipitation_mm"]
        else:
            norm["rainfall_mm"] = None

        return norm

    def _normalize_hourly(
        self,
        hourly: dict[str, Any],
        req_lat: float,
        req_lon: float,
        issue_time: datetime,
        ref_now: datetime,
    ) -> list[dict[str, Any]]:
        """Parses parallel arrays in the 'hourly' block into normalized item records."""
        time_list = hourly.get("time") or []
        if not isinstance(time_list, list):
            return []

        num_hours = len(time_list)
        records: list[dict[str, Any]] = []

        for i in range(num_hours):
            t_str = time_list[i]
            valid_time = parse_utc_timestamp(t_str)

            # Classify OBSERVATION (past/present) vs FORECAST (future)
            data_type = "FORECAST" if valid_time > ref_now else "OBSERVATION"

            rec: dict[str, Any] = {
                "provider": self.name,
                "data_type": data_type,
                "latitude": round(req_lat, 4),
                "longitude": round(req_lon, 4),
                "observed_at": issue_time if data_type == "FORECAST" else valid_time,
                "forecast_valid_at": valid_time,
                "issue_time": issue_time,
            }

            def _get_val(key: str) -> Any:
                arr = hourly.get(key)
                if arr and isinstance(arr, list) and i < len(arr):
                    return arr[i]
                return None

            temp = _get_val("temperature_2m")
            if temp is not None:
                rec["temperature_c"] = float(temp)

            app_temp = _get_val("apparent_temperature")
            if app_temp is not None:
                rec["apparent_temperature_c"] = float(app_temp)

            rh = _get_val("relative_humidity_2m")
            if rh is not None:
                rec["relative_humidity_pct"] = float(rh)

            dp = _get_val("dew_point_2m")
            if dp is not None:
                rec["dew_point_c"] = float(dp)

            precip = _get_val("precipitation")
            if precip is not None:
                rec["precipitation_mm"] = float(precip)
                rec["rainfall_mm"] = float(precip)

            rain = _get_val("rain")
            if rain is not None:
                rec["rain_mm"] = float(rain)
                if "rainfall_mm" not in rec:
                    rec["rainfall_mm"] = float(rain)

            showers = _get_val("showers")
            if showers is not None:
                rec["showers_mm"] = float(showers)

            snowfall = _get_val("snowfall")
            if snowfall is not None:
                rec["snowfall_cm"] = float(snowfall)

            precip_prob = _get_val("precipitation_probability")
            if precip_prob is not None:
                rec["precipitation_probability_pct"] = float(precip_prob)

            ws = _get_val("wind_speed_10m")
            if ws is not None:
                rec["wind_speed_kmh"] = float(ws)

            wd = _get_val("wind_direction_10m")
            if wd is not None:
                rec["wind_direction_deg"] = float(wd)

            wg = _get_val("wind_gusts_10m")
            if wg is not None:
                rec["wind_gusts_kmh"] = float(wg)

            p_msl = _get_val("pressure_msl")
            if p_msl is not None:
                rec["pressure_msl_hpa"] = float(p_msl)

            p_sfc = _get_val("surface_pressure")
            if p_sfc is not None:
                rec["surface_pressure_hpa"] = float(p_sfc)

            vis = _get_val("visibility")
            if vis is not None:
                rec["visibility_m"] = float(vis)

            wcode = _get_val("weather_code")
            if wcode is not None:
                rec["weather_code"] = int(wcode)

            cc = _get_val("cloud_cover")
            if cc is not None:
                rec["cloud_cover_pct"] = float(cc)

            soil_m = _get_val("soil_moisture_0_to_7cm")
            if soil_m is not None:
                rec["soil_moisture_m3m3"] = float(soil_m)

            et0 = _get_val("et0_fao_evapotranspiration")
            if et0 is not None:
                rec["et0_evapotranspiration_mm"] = float(et0)

            records.append(rec)

        return records

    def _normalize_daily(self, daily: dict[str, Any]) -> list[dict[str, Any]]:
        """Parses parallel arrays in the 'daily' block into daily summary dictionaries."""
        time_list = daily.get("time") or []
        if not isinstance(time_list, list):
            return []

        summaries: list[dict[str, Any]] = []
        for i in range(len(time_list)):
            d_str = time_list[i]

            def _get_d(key: str) -> Any:
                arr = daily.get(key)
                if arr and isinstance(arr, list) and i < len(arr):
                    return arr[i]
                return None

            item: dict[str, Any] = {
                "date": str(d_str),
                "weather_code": int(_get_d("weather_code")) if _get_d("weather_code") is not None else None,
                "temperature_2m_max_c": float(_get_d("temperature_2m_max")) if _get_d("temperature_2m_max") is not None else None,
                "temperature_2m_min_c": float(_get_d("temperature_2m_min")) if _get_d("temperature_2m_min") is not None else None,
                "apparent_temperature_max_c": float(_get_d("apparent_temperature_max")) if _get_d("apparent_temperature_max") is not None else None,
                "apparent_temperature_min_c": float(_get_d("apparent_temperature_min")) if _get_d("apparent_temperature_min") is not None else None,
                "precipitation_sum_mm": float(_get_d("precipitation_sum")) if _get_d("precipitation_sum") is not None else None,
                "rain_sum_mm": float(_get_d("rain_sum")) if _get_d("rain_sum") is not None else None,
                "showers_sum_mm": float(_get_d("showers_sum")) if _get_d("showers_sum") is not None else None,
                "snowfall_sum_cm": float(_get_d("snowfall_sum")) if _get_d("snowfall_sum") is not None else None,
                "precipitation_probability_max_pct": float(_get_d("precipitation_probability_max")) if _get_d("precipitation_probability_max") is not None else None,
                "wind_speed_10m_max_kmh": float(_get_d("wind_speed_10m_max")) if _get_d("wind_speed_10m_max") is not None else None,
                "wind_gusts_10m_max_kmh": float(_get_d("wind_gusts_10m_max")) if _get_d("wind_gusts_10m_max") is not None else None,
                "sunrise": str(_get_d("sunrise")) if _get_d("sunrise") is not None else None,
                "sunset": str(_get_d("sunset")) if _get_d("sunset") is not None else None,
            }
            summaries.append(item)

        return summaries
