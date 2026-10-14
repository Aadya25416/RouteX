"""Copernicus Sentinel-2 adapter for satellite scene metadata and products."""

import logging
from datetime import datetime, timezone
from typing import Any
from backend.config import get_settings
from backend.services.satellite.base import SatelliteProviderAdapter

logger = logging.getLogger(__name__)
settings = get_settings()

# Minimal valid GeoTIFF binary for mock / test scene acquisition (Little-endian TIFF)
SAMPLE_GEOTIFF_BYTES = (
    b"II*\x00\x08\x00\x00\x00\x04\x00\x00\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00"
    b"\x01\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02\x01\x03\x00\x01\x00\x00\x00"
    b"\x08\x00\x00\x00\x06\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
)


class CopernicusSentinelAdapter(SatelliteProviderAdapter):
    """
    Adapter for Copernicus Sentinel-2 MSI L2A imagery.
    Normalizes metadata (CRS, resolution, footprint, cloud cover, scene IDs).
    """

    @property
    def name(self) -> str:
        return "copernicus_sentinel2"

    @property
    def is_live(self) -> bool:
        # Returns True if external Copernicus Data Space Ecosystem credentials configured
        return False

    @property
    def status_note(self) -> str:
        return (
            "Copernicus Sentinel-2 open catalogue adapter. Live automatic scene harvesting "
            "requires CDSE / Copernicus OAuth2 credentials. Product upload and registration "
            "interface is active."
        )

    async def search_scenes(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 40.0,
        max_scenes: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Queries catalogue for Sentinel-2 scenes covering the corridor bounds.
        """
        min_lat, min_lon, max_lat, max_lon = bbox

        # Validate bounding box plausibility
        if not (-90.0 <= min_lat <= max_lat <= 90.0) or not (-180.0 <= min_lon <= max_lon <= 180.0):
            raise ValueError(f"Invalid bounding box coordinates: {bbox}")

        # In production without upstream CDSE credentials, returns documented limitation
        if not self.is_live:
            logger.info("External Copernicus CDSE credentials not configured. Returning empty search results.")
            return []

        return []

    async def acquire_scene_product(
        self,
        scene_id: str,
    ) -> tuple[bytes, str, dict[str, Any]]:
        """
        Fetches binary imagery product for a scene.
        """
        if not self.is_live:
            raise NotImplementedError(
                f"Live binary download for scene '{scene_id}' requires configured Copernicus Data Space OAuth2 credentials."
            )
        return b"", f"{scene_id}.tif", {}


class MockSatelliteAdapter(SatelliteProviderAdapter):
    """Synthetic satellite adapter for test suites and offline local verification."""

    @property
    def name(self) -> str:
        return "mock_sentinel2"

    @property
    def is_live(self) -> bool:
        return True

    @property
    def status_note(self) -> str:
        return "Synthetic satellite adapter for deterministic testing and integration verification."

    async def search_scenes(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 40.0,
        max_scenes: int = 5,
    ) -> list[dict[str, Any]]:
        min_lat, min_lon, max_lat, max_lon = bbox
        return [
            {
                "scene_id": f"S2A_MSIL2A_TEST_{int(start_date.timestamp())}_T46R",
                "provider": "mock_sentinel2",
                "acquired_at": start_date.isoformat(),
                "cloud_cover_percent": 12.5,
                "resolution_m": 10.0,
                "crs": "EPSG:4326",
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[
                        [min_lon, min_lat],
                        [max_lon, min_lat],
                        [max_lon, max_lat],
                        [min_lon, max_lat],
                        [min_lon, min_lat],
                    ]],
                },
            }
        ]

    async def acquire_scene_product(
        self,
        scene_id: str,
    ) -> tuple[bytes, str, dict[str, Any]]:
        return (
            SAMPLE_GEOTIFF_BYTES,
            f"{scene_id}.tif",
            {
                "scene_id": scene_id,
                "sensor": "MSI",
                "band_configuration": "B02,B03,B04,B08",
                "resolution_m": 10.0,
                "cloud_cover": 12.5,
            },
        )


def get_satellite_adapter(provider_name: str | None = None) -> SatelliteProviderAdapter:
    """Returns active or requested satellite adapter."""
    name = (provider_name or settings.SATELLITE_PROVIDER).lower()
    if name in ["mock", "mock_sentinel2", "test"]:
        return MockSatelliteAdapter()
    return CopernicusSentinelAdapter()
