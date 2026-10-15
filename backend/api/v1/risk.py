"""FastAPI endpoints for Road Risk Scoring, ML Predictions, and Segment Health Assessments."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.risk import RoadRiskEvaluationRequest, RoadRiskItem, RoadRiskListResponse
from backend.services.risk_service import RiskService

router = APIRouter(prefix="/risk", tags=["Road Risk & Safety Scoring"])


@router.get("", response_model=RoadRiskListResponse, status_code=status.HTTP_200_OK)
async def get_road_risk(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    min_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="South bounding latitude")] = None,
    min_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="West bounding longitude")] = None,
    max_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="North bounding latitude")] = None,
    max_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="East bounding longitude")] = None,
    road_segment_ids: Annotated[list[str] | None, Query(description="Filter by specific road segment IDs")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by operational status")] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Maximum number of road risk records")] = 100,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> RoadRiskListResponse:
    """
    Exposes segment-level operational risk scores, disruption probabilities, and ML metadata.

    Score Semantics:
    - `safety_score`: 0–100 convention, where 100 means safer and 0 means least safe.
    - `disruption_probability`: 0.0–1.0 disruption probability produced by XGBoost models.
    - `score_type`: Distinguishes 'ml_probabilistic', 'authoritative_incident', and 'unknown'.
    - `is_stale`: True if prediction timestamp is beyond configured validity horizon.
    - `is_unknown`: True if segment lacks evaluated ML risk data (never fabricated as safe).

    Authoritative Precedence:
    - Authoritative confirmed closures (status=BLOCKED) always override model scores.
    """
    service = RiskService(session)
    try:
        return await service.get_road_risk(
            min_lat=min_lat,
            min_lon=min_lon,
            max_lat=max_lat,
            max_lon=max_lon,
            road_segment_ids=road_segment_ids,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
    finally:
        service.close()


@router.get("/{road_segment_id}", response_model=RoadRiskItem, status_code=status.HTTP_200_OK)
async def get_segment_risk(
    road_segment_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RoadRiskItem:
    """Retrieves operational safety score and model explanation factors for a single road segment."""
    service = RiskService(session)
    try:
        return await service.get_segment_risk_detail(road_segment_id=road_segment_id)
    finally:
        service.close()


@router.post("/evaluate", response_model=RoadRiskItem, status_code=status.HTTP_200_OK)
async def evaluate_segment_risk_endpoint(
    payload: RoadRiskEvaluationRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker"]))],
) -> RoadRiskItem:
    """
    Explicitly triggers the unified ML inference pipeline (XGBoost landslide + delay regressor)
    with fresh weather observations and terrain metrics, persisting updated predictions.
    """
    service = RiskService(session)
    try:
        await service.evaluate_segment_risk(
            road_segment_id=payload.road_segment_id,
            actor_id=current_user.id,
            force_reeval=True,
        )
        return await service.get_segment_risk_detail(road_segment_id=payload.road_segment_id)
    finally:
        service.close()
