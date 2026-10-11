"""CLI command to download and import a configurable OSM road network corridor."""

import argparse
import logging
import sys
from backend.config import get_settings
from backend.services.osm_importer import OSMImporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("osm_importer_cli")


def main():
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Download and ingest an OpenStreetMap road network into PostGIS."
    )
    parser.add_argument(
        "--south",
        type=float,
        default=settings.CORRIDOR_MIN_LAT,
        help=f"South latitude (default: {settings.CORRIDOR_MIN_LAT})",
    )
    parser.add_argument(
        "--west",
        type=float,
        default=settings.CORRIDOR_MIN_LON,
        help=f"West longitude (default: {settings.CORRIDOR_MIN_LON})",
    )
    parser.add_argument(
        "--north",
        type=float,
        default=settings.CORRIDOR_MAX_LAT,
        help=f"North latitude (default: {settings.CORRIDOR_MAX_LAT})",
    )
    parser.add_argument(
        "--east",
        type=float,
        default=settings.CORRIDOR_MAX_LON,
        help=f"East longitude (default: {settings.CORRIDOR_MAX_LON})",
    )
    parser.add_argument(
        "--network-type",
        type=str,
        default=settings.OSM_NETWORK_TYPE,
        help=f"OSM network type (default: {settings.OSM_NETWORK_TYPE})",
    )
    parser.add_argument(
        "--corridor-name",
        type=str,
        default=settings.CORRIDOR_NAME,
        help=f"Corridor identifier name (default: {settings.CORRIDOR_NAME})",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=None,
        help="Optional path to save or load GraphML file cache",
    )

    args = parser.parse_args()

    if args.south >= args.north or args.west >= args.east:
        logger.error("Invalid coordinates: south must be < north and west must be < east")
        sys.exit(1)

    bbox = (args.south, args.west, args.north, args.east)
    logger.info(f"Target corridor: {args.corridor_name} {bbox}")

    importer = OSMImporter(settings=settings)
    try:
        graph = importer.fetch_graph(
            bbox=bbox,
            network_type=args.network_type,
            cache_path=args.cache_file,
        )
        results = importer.persist_graph(graph=graph, corridor_name=args.corridor_name)
        logger.info(f"Import summary: {results}")
        logger.info("Attribution: © OpenStreetMap contributors under ODbL")
    except Exception as exc:
        logger.error(f"Import failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
