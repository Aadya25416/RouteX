"""Abstract weather provider interface for external meteorological feeds."""

import abc
from datetime import datetime
from typing import Any


class WeatherProvider(abc.ABC):
    """Abstract interface for weather providers allowing Open-Meteo, IMD, or custom feeds."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abc.abstractmethod
    async def fetch_current_observation(self, lat: float, lon: float) -> dict[str, Any]:
        """
        Retrieves current conditions for latitude and longitude.
        Returns normalized dictionary with non-null values for only fields provided upstream.
        """
        pass

    @abc.abstractmethod
    async def fetch_weather(
        self,
        lat: float,
        lon: float,
        forecast_days: int = 2,
    ) -> dict[str, Any]:
        """
        Retrieves current, hourly forecast, and daily summary data for latitude and longitude.
        Returns:
            {
                "current": dict[str, Any],
                "hourly": list[dict[str, Any]],
                "daily": list[dict[str, Any]],
                "metadata": dict[str, Any],
            }
        """
        pass
