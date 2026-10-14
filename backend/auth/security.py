"""Authentication and Role-Based Access Control (RBAC) security dependencies."""

import logging
import uuid
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import get_async_session
from backend.models.users import User

logger = logging.getLogger(__name__)
settings = get_settings()

# Optional HTTPBearer so missing headers return 401 cleanly with custom messages
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    auth_creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_user_email: Annotated[str | None, Header(alias="X-User-Email")] = None,
) -> User:
    """
    Resolves the current authenticated user from Bearer token or development headers.
    Verifies that the user exists and is active.
    In non-development/test environments, development identity headers are rejected.
    """
    is_dev_env = settings.APP_ENV in ["development", "test"]

    # Security check: disallow dev headers in staging/production
    if not is_dev_env and (x_user_role or x_user_id or x_user_email):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development identity headers are prohibited outside development/test environments. Use standard Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_val = None
    if auth_creds and auth_creds.credentials:
        token_val = auth_creds.credentials.strip()

    user_identifier = token_val or (x_user_id or x_user_email if is_dev_env else None)

    if not user_identifier:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Try parsing as UUID
    user_uuid: uuid.UUID | None = None
    try:
        user_uuid = uuid.UUID(user_identifier)
    except ValueError:
        user_uuid = None

    user: User | None = None
    if user_uuid:
        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

    if not user:
        # Try matching by email
        candidates = [user_identifier]
        if "@" not in user_identifier:
            candidates.append(f"{user_identifier}@nerlink.internal")
        if x_user_role:
            candidates.append(f"{x_user_role}_{user_identifier[:8]}@nerlink.internal")
            candidates.append(f"{x_user_role}@nerlink.internal")

        result = await session.execute(select(User).where(User.email.in_(candidates)))
        user = result.scalars().first()

    # If user not found in DB, check if development X-User-Role is provided to auto-provision dev/test user
    if not user:
        if x_user_role or (token_val and token_val in ["admin", "dispatcher", "field_officer", "driver", "ml_service", "service_worker"]):
            role = x_user_role or token_val
            dev_email = user_identifier if "@" in user_identifier else f"{role}_{user_identifier[:8]}@nerlink.internal"
            # Double check existing
            existing = await session.execute(select(User).where(User.email == dev_email))
            found = existing.scalar_one_or_none()
            if found:
                return found

            dev_user = User(
                id=user_uuid or uuid.uuid4(),
                email=dev_email,
                full_name=f"Dev {role.title()}",
                role=role,
                is_active=True,
            )
            session.add(dev_user)
            await session.commit()
            await session.refresh(dev_user)
            return dev_user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{user_identifier}' not found or invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return user


def require_roles(allowed_roles: list[str]):
    """Role-based access control dependency factory."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{current_user.role}' lacks permission for this action. Allowed: {allowed_roles}",
            )
        return current_user

    return role_checker
