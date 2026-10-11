"""Database and cache connections and session management."""

import logging
from typing import AsyncGenerator
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
import redis.asyncio as aioredis
from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

import sys
from sqlalchemy.pool import NullPool

# Asynchronous engine for FastAPI web handlers
is_test = "pytest" in sys.modules or settings.APP_ENV == "test"
async_engine_kwargs = {"echo": False, "pool_pre_ping": True}
if is_test:
    async_engine_kwargs["poolclass"] = NullPool
else:
    async_engine_kwargs["pool_size"] = 10
    async_engine_kwargs["max_overflow"] = 20

async_engine = create_async_engine(
    settings.database_url_async,
    **async_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Synchronous engine for Alembic migrations, management CLI and bulk operations
sync_engine = create_engine(
    settings.database_url_sync,
    echo=False,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> dict:
    """Verifies PostgreSQL connectivity and PostGIS extension version."""
    try:
        async with async_engine.connect() as conn:
            # Query standard PostgreSQL version
            pg_res = await conn.execute(text("SELECT version();"))
            pg_version = pg_res.scalar()

            # Query PostGIS version
            try:
                gis_res = await conn.execute(text("SELECT PostGIS_Full_Version();"))
                postgis_version = gis_res.scalar()
                has_postgis = True
            except Exception as gis_err:
                logger.warning(f"PostGIS extension check failed: {gis_err}")
                postgis_version = None
                has_postgis = False

            return {
                "status": "connected" if has_postgis else "degraded",
                "postgresql_version": pg_version,
                "has_postgis": has_postgis,
                "postgis_version": postgis_version,
            }
    except Exception as exc:
        logger.error(f"Database connection failed: {exc}")
        return {
            "status": "disconnected",
            "error": str(exc),
            "has_postgis": False,
        }


async def check_redis_connection() -> dict:
    """Verifies Redis connectivity and ping response."""
    try:
        client = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=2.0,
            decode_responses=True,
        )
        pong = await client.ping()
        await client.aclose()
        return {
            "status": "connected" if pong else "degraded",
            "ping": bool(pong),
        }
    except Exception as exc:
        logger.warning(f"Redis connection failed: {exc}")
        return {
            "status": "disconnected",
            "error": str(exc),
            "ping": False,
        }
