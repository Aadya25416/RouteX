"""FastAPI endpoints exposing the Machine Learning pipeline integration contract."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.ml import (
    MLClaimRequest,
    MLEvidenceTaskResponse,
    MLPendingQueueResponse,
    MLResultSubmissionRequest,
)
from backend.services.evidence_service import EvidenceService, to_ml_task_response
from backend.services.storage import get_storage_service

router = APIRouter(prefix="/ml/evidence", tags=["ML Pipeline Integration"])


@router.get("/pending", response_model=MLPendingQueueResponse)
async def get_pending_evidence(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["ml_service", "service_worker", "dispatcher", "admin"]))],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    source_type: Annotated[str | None, Query(description="Filter by FIELD_OFFICER, SATELLITE, etc.")] = None,
) -> MLPendingQueueResponse:
    """
    Discovers pending evidence tasks awaiting computer vision and road-damage inference.
    Includes both PENDING items and expired IN_PROGRESS leases available for recovery.
    """
    service = EvidenceService(session)
    tasks = await service.get_pending_tasks(limit=limit, source_type=source_type)
    return MLPendingQueueResponse(
        total_pending=len(tasks),
        tasks=[to_ml_task_response(t) for t in tasks],
    )


@router.post("/{evidence_id}/claim", response_model=MLEvidenceTaskResponse)
async def claim_evidence_task(
    evidence_id: uuid.UUID,
    payload: MLClaimRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["ml_service", "service_worker", "dispatcher", "admin"]))],
) -> MLEvidenceTaskResponse:
    """
    Atomically claims an evidence task for an ML worker instance.
    Prevents race conditions where multiple workers process the same image concurrently.
    """
    service = EvidenceService(session)
    evidence = await service.claim_task(evidence_id=evidence_id, worker_id=payload.worker_id)
    return to_ml_task_response(evidence)


@router.post("/{evidence_id}/result", response_model=MLEvidenceTaskResponse)
async def submit_ml_result(
    evidence_id: uuid.UUID,
    payload: MLResultSubmissionRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["ml_service", "service_worker", "dispatcher", "admin"]))],
) -> MLEvidenceTaskResponse:
    """
    Reports completion or failure of ML inference for an evidence task.
    Updates detection class, confidence, bounding boxes, or operational error state.
    """
    service = EvidenceService(session)
    evidence = await service.submit_task_result(
        evidence_id=evidence_id,
        worker_id=payload.worker_id,
        status_val=payload.status,
        model_detection_class=payload.model_detection_class,
        model_confidence=payload.model_confidence,
        model_metadata=payload.model_metadata,
        error_message=payload.error_message,
    )
    return to_ml_task_response(evidence)


@router.get("/{evidence_id}/download")
async def download_evidence_for_ml(
    evidence_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["ml_service", "service_worker", "dispatcher", "admin"]))],
) -> Response:
    """Provides authenticated image binary retrieval for authorized ML workers."""
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id)

    if not evidence.stored_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence binary reference for '{evidence_id}' not found.",
        )

    storage = get_storage_service()
    content, mime = await storage.get_evidence_file(evidence.stored_filename)

    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{evidence.original_filename or "evidence.jpg"}"'},
    )
