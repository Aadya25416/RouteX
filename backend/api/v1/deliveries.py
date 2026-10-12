"""Essential supplies delivery consignment endpoints."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.logistics import Delivery
from backend.models.users import User
from backend.schemas.logistics import (
    DeliveryCreateRequest,
    DeliveryListResponse,
    DeliveryResponse,
    DeliveryUpdateRequest,
)
from backend.services.logistics_service import LogisticsService

router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


async def _to_delivery_response(deliv: Delivery, session: AsyncSession) -> DeliveryResponse:
    coords_res = await session.execute(
        select(
            func.ST_Y(deliv.origin_geom).label("orig_lat"),
            func.ST_X(deliv.origin_geom).label("orig_lon"),
            func.ST_Y(deliv.destination_geom).label("dest_lat"),
            func.ST_X(deliv.destination_geom).label("dest_lon"),
        ).where(Delivery.id == deliv.id)
    )
    coords = coords_res.first()

    return DeliveryResponse(
        id=deliv.id,
        tracking_code=deliv.tracking_code,
        cargo_type=deliv.cargo_type,
        cargo_class=deliv.cargo_class,
        description=deliv.description,
        priority=deliv.priority,
        origin_address=deliv.origin_address,
        origin_name=deliv.origin_name,
        origin_lat=float(coords.orig_lat) if coords and coords.orig_lat is not None else None,
        origin_lon=float(coords.orig_lon) if coords and coords.orig_lon is not None else None,
        destination_address=deliv.destination_address,
        destination_name=deliv.destination_name,
        destination_lat=float(coords.dest_lat) if coords and coords.dest_lat is not None else None,
        destination_lon=float(coords.dest_lon) if coords and coords.dest_lon is not None else None,
        deadline=deliv.deadline,
        status=deliv.status,
        created_at=deliv.created_at,
        updated_at=deliv.updated_at,
    )


@router.post("", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery(
    payload: DeliveryCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> DeliveryResponse:
    """Creates a new essential supply consignment. Requires dispatcher or admin role."""
    service = LogisticsService(session)
    deliv = await service.create_delivery(payload, actor_id=current_user.id)
    return await _to_delivery_response(deliv, session)


@router.get("", response_model=DeliveryListResponse)
async def list_deliveries(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[str | None, Query(description="Filter by delivery status")] = None,
    cargo_type: Annotated[str | None, Query(description="Filter by cargo type")] = None,
    priority: Annotated[str | None, Query(description="Filter by priority")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DeliveryListResponse:
    """Lists delivery consignments with filtering."""
    service = LogisticsService(session)
    total, items = await service.list_deliveries(
        status_filter=status,
        cargo_type=cargo_type,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    res_items = []
    for d in items:
        res_items.append(await _to_delivery_response(d, session))
    return DeliveryListResponse(total=total, items=res_items)


@router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DeliveryResponse:
    """Retrieves delivery consignment details."""
    service = LogisticsService(session)
    deliv = await service.get_delivery(delivery_id)
    return await _to_delivery_response(deliv, session)


@router.patch("/{delivery_id}", response_model=DeliveryResponse)
async def update_delivery(
    delivery_id: uuid.UUID,
    payload: DeliveryUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> DeliveryResponse:
    """Updates delivery attributes or lifecycle status. Requires dispatcher or admin role."""
    service = LogisticsService(session)
    deliv = await service.update_delivery(delivery_id, payload, actor_id=current_user.id)
    return await _to_delivery_response(deliv, session)
