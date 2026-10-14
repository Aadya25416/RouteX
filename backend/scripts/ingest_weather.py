"""CLI script to trigger weather data collection across the corridor."""

import asyncio
import logging
import sys

from backend.database import AsyncSessionLocal
from backend.services.weather.weather_service import WeatherService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weather_ingest_cli")


async def run_weather_ingest():
    logger.info("Starting corridor meteorological observation ingestion run...")
    async with AsyncSessionLocal() as session:
        service = WeatherService(session)
        summary = await service.refresh_corridor_weather()
        logger.info(
            f"Weather refresh completed: {summary.observations_persisted} observations persisted "
            f"across {summary.sample_points_queried} sample points in {summary.duration_seconds}s."
        )


def main():
    try:
        asyncio.run(run_weather_ingest())
    except KeyboardInterrupt:
        logger.info("Weather ingestion aborted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Weather ingestion failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
