"""NER-LINK FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.health import router as health_router
from backend.api.v1.router import api_v1_router
from backend.config import get_settings
from backend.database import check_database_connection, check_redis_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nerlink.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown procedures."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode...")
    logger.info(f"Corridor configured: {settings.CORRIDOR_NAME} {settings.corridor_bbox}")

    # Inspect initial connectivity
    db_health = await check_database_connection()
    logger.info(f"PostgreSQL status: {db_health.get('status')}, PostGIS: {db_health.get('has_postgis')}")
    redis_health = await check_redis_connection()
    logger.info(f"Redis status: {redis_health.get('status')}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application."""
    app = FastAPI(
        title="NER-LINK API",
        description=(
            "Logistics Accessibility Intelligence Platform for the North Eastern Region. "
            "Provides road accessibility intelligence, disruption management, and routable road graph APIs."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoints at root level
    app.include_router(health_router)

    # Versioned API routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "environment": settings.APP_ENV,
            "docs": "/docs",
            "corridor": {
                "name": settings.CORRIDOR_NAME,
                "bbox": {
                    "south": settings.CORRIDOR_MIN_LAT,
                    "west": settings.CORRIDOR_MIN_LON,
                    "north": settings.CORRIDOR_MAX_LAT,
                    "east": settings.CORRIDOR_MAX_LON,
                },
            },
            "attribution": "Road network data © OpenStreetMap contributors under ODbL",
        }

    return app


app = create_app()
