"""CLI script to trigger weather data collection and forecast ingestion across the corridor."""

import argparse
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


async def run_weather_ingest(forecast_days: int = 2):
    logger.info(f"Starting corridor meteorological ingestion run ({forecast_days} forecast days)...")
    async with AsyncSessionLocal() as session:
        service = WeatherService(session)
        summary = await service.refresh_corridor_weather(forecast_days=forecast_days)
        logger.info(
            f"Weather refresh completed in {summary.duration_seconds}s: "
            f"{summary.current_observations_persisted} current observations, "
            f"{summary.forecast_records_persisted} forecast records "
            f"({summary.observations_persisted} total) across {summary.sample_points_queried} sample points."
        )


def main():
    parser = argparse.ArgumentParser(description="Trigger corridor weather data collection.")
    parser.add_argument(
        "--forecast-days",
        type=int,
        default=2,
        help="Number of forecast days to fetch (1-7, default: 2)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_weather_ingest(forecast_days=args.forecast_days))
    except KeyboardInterrupt:
        logger.info("Weather ingestion aborted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Weather ingestion failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
