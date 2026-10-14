"""Abstract interface for external satellite imagery providers."""

import abc
from datetime import datetime
from typing import Any


class SatelliteProviderAdapter(abc.ABC):
    """Pluggable adapter interface for remote sensing and satellite data sources."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'copernicus_sentinel2', 'usgs_landsat8')."""
        pass

    @property
    @abc.abstractmethod
    def is_live(self) -> bool:
        """Indicates whether this adapter connects to a genuine live upstream provider."""
        pass

    @property
    @abc.abstractmethod
    def status_note(self) -> str:
        """Documented operational status or limitations of this provider."""
        pass

    @abc.abstractmethod
    async def search_scenes(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 40.0,
        max_scenes: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Discovers satellite scenes matching geographical and temporal filters.
        Returns normalized metadata dicts containing scene_id, footprint, acquired_at, etc.
        """
        pass

    @abc.abstractmethod
    async def acquire_scene_product(
        self,
        scene_id: str,
    ) -> tuple[bytes, str, dict[str, Any]]:
        """
        Fetches the imagery product binary and normalized metadata for a scene.
        Returns: (image_bytes, suggested_filename, normalized_metadata)
        """
        pass
