"""API v1 Router aggregation."""

from fastapi import APIRouter
from backend.api.v1.incidents import router as incidents_router
from backend.api.v1.roads import router as roads_router

api_v1_router = APIRouter()
api_v1_router.include_router(roads_router)
api_v1_router.include_router(incidents_router)

