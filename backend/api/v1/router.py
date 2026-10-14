"""API v1 Router aggregation."""

from fastapi import APIRouter
from backend.api.v1.deliveries import router as deliveries_router
from backend.api.v1.evidence import router as evidence_router
from backend.api.v1.incidents import router as incidents_router
from backend.api.v1.ml import router as ml_router
from backend.api.v1.roads import router as roads_router
from backend.api.v1.routes import router as routes_router
from backend.api.v1.satellite import router as satellite_router
from backend.api.v1.traffic import router as traffic_router
from backend.api.v1.trips import router as trips_router
from backend.api.v1.vehicles import router as vehicles_router
from backend.api.v1.weather import router as weather_router

api_v1_router = APIRouter()
api_v1_router.include_router(roads_router)
api_v1_router.include_router(incidents_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(ml_router)
api_v1_router.include_router(satellite_router)
api_v1_router.include_router(weather_router)
api_v1_router.include_router(traffic_router)
api_v1_router.include_router(vehicles_router)
api_v1_router.include_router(deliveries_router)
api_v1_router.include_router(trips_router)
api_v1_router.include_router(routes_router)

