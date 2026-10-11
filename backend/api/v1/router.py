"""API v1 Router aggregation."""

from fastapi import APIRouter
from backend.api.v1.roads import router as roads_router

api_v1_router = APIRouter()
api_v1_router.include_router(roads_router)
