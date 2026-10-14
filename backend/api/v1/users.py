"""Administrative User Management and Account Lifecycle Endpoints."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.auth import (
    PasswordResetRequest,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["admin"]))],
) -> UserResponse:
    """
    Administrative creation of an authorized user account with specified role and credentials.
    Anonymous registration of privileged administrative roles is prohibited.
    """
    service = AuthService(session)
    user = await service.create_user(payload=payload, actor=current_user)
    return UserResponse.model_validate(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["admin"]))],
    role: Annotated[str | None, Query(description="Filter by role")] = None,
    is_active: Annotated[bool | None, Query(description="Filter active status")] = None,
    search: Annotated[str | None, Query(description="Search email or full name")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    """
    Lists user accounts with role, status, and search filtering. Restricted to administrators.
    Never exposes password hashes or security secrets.
    """
    service = AuthService(session)
    total, users = await service.list_users(
        role=role,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return UserListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[UserResponse.model_validate(u) for u in users],
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Retrieves user profile details.
    Users may view their own profile; administrators may view any account.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you lack permission to view this user profile.",
        )

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Updates user account attributes.
    Modifying role or active status requires admin privileges.
    Deactivating an account immediately revokes all active sessions.
    """
    service = AuthService(session)
    updated = await service.update_user(user_id=user_id, payload=payload, actor=current_user)
    return UserResponse.model_validate(updated)


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Resets account password and invalidates all existing active sessions.
    Administrators can reset any user; non-admins may only reset their own credentials.
    """
    service = AuthService(session)
    updated = await service.reset_password(user_id=user_id, payload=payload, actor=current_user)
    return UserResponse.model_validate(updated)
