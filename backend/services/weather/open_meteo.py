"""Open-Meteo weather provider implementation."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
import httpx

from backend.config import get_settings
from backend.services.weather.base import WeatherProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Genuine external meteorological feed using the Open-Meteo API.
    Supports temperature, precipitation, wind speed/gusts, visibility, and WMO codes.
    """

    def __init__(self, api_url: str | None = None, timeout_seconds: float | None = None):
        self.api_url = api_url or settings.OPEN_METEO_API_URL
        self.timeout = timeout_seconds or settings.WEATHER_REQUEST_TIMEOUT_SECONDS

    @property
    def name(self) -> str:
        return "open-meteo"

    async def fetch_current_observation(self, lat: float, lon: float) -> dict[str, Any]:
        """
        Fetches current weather from Open-Meteo with retry handling.
        """
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "current": "temperature_2m,precipitation,rain,snowfall,weather_code,wind_speed_10m,wind_gusts_10m,visibility",
            "timezone": "UTC",
        }

        last_error = None
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(self.api_url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        return self._normalize_response(data, lat, lon)
                    elif resp.status_code >= 500:
                        last_error = f"Upstream HTTP {resp.status_code}: {resp.text}"
                    else:
                        resp.raise_for_status()
            except httpx.RequestError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc)

            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)

        raise RuntimeError(f"Open-Meteo request failed after 3 attempts for ({lat}, {lon}): {last_error}")

    def _normalize_response(self, data: dict[str, Any], req_lat: float, req_lon: float) -> dict[str, Any]:
        """
        Extracts and normalizes available fields without fabricating missing data.
        """
        current = data.get("current", {})
        if not current:
            raise ValueError(f"Malformed Open-Meteo payload missing 'current' block: {data}")

        # Parse observation timestamp
        time_str = current.get("time")
        if time_str:
            if not time_str.endswith("Z") and "+" not in time_str:
                time_str += "+00:00"
            observed_at = datetime.fromisoformat(time_str)
        else:
            observed_at = datetime.now(timezone.utc)

        # Do NOT convert missing/null fields to 0.0
        normalized = {
            "provider": self.name,
            "latitude": req_lat,
            "longitude": req_lon,
            "observed_at": observed_at,
            "forecast_valid_at": observed_at,
            "raw_payload": data,
        }

        if "temperature_2m" in current and current["temperature_2m"] is not None:
            normalized["temperature_c"] = float(current["temperature_2m"])

        # Rainfall / precipitation
        if "rain" in current and current["rain"] is not None:
            normalized["rainfall_mm"] = float(current["rain"])
        elif "precipitation" in current and current["precipitation"] is not None:
            normalized["rainfall_mm"] = float(current["precipitation"])

        if "wind_speed_10m" in current and current["wind_speed_10m"] is not None:
            normalized["wind_speed_kmh"] = float(current["wind_speed_10m"])

        if "wind_gusts_10m" in current and current["wind_gusts_10m"] is not None:
            normalized["wind_gusts_kmh"] = float(current["wind_gusts_10m"])

        if "snowfall" in current and current["snowfall"] is not None:
            normalized["snowfall_cm"] = float(current["snowfall"])

        if "visibility" in current and current["visibility"] is not None:
            normalized["visibility_m"] = float(current["visibility"])

        if "weather_code" in current and current["weather_code"] is not None:
            normalized["weather_code"] = int(current["weather_code"])

        return normalized
