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
    Resolves the current authenticated user from Bearer JWT access token or development headers.
    - Validates signature, expiration, issuer, and claims of JWT.
    - In production/staging, development headers are rejected immediately.
    - Ensures headers cannot override an authenticated Bearer token.
    - Verifies the user exists in database and is active.
    """
    from backend.auth.crypto import decode_access_token

    is_dev_allowed = (
        settings.APP_ENV in ["development", "test"]
        and settings.ALLOW_DEV_AUTH_HEADERS is True
    )

    # 1. First priority: Authenticate via Bearer JWT token if present
    if auth_creds and auth_creds.credentials:
        token_str = auth_creds.credentials.strip()
        try:
            payload = decode_access_token(token_str)
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token claims: subject ('sub') is required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            try:
                user_uuid = uuid.UUID(user_id_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token claims: subject ('sub') must be a valid UUID.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            res = await session.execute(select(User).where(User.id == user_uuid))
            user = res.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User associated with this token does not exist.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is deactivated.",
                )
            return user
        except HTTPException:
            # If token is a JWT (contains 2 dots) or we are outside dev, raise immediately
            if not is_dev_allowed or token_str.count(".") == 2:
                raise
            # Otherwise, allow dev fallback below if in dev/test environment

    # 2. Check for development headers
    has_dev_headers = bool(x_user_role or x_user_id or x_user_email)

    # Outside dev/test or when dev headers are disabled, reject headers or missing auth
    if not is_dev_allowed:
        if has_dev_headers:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Development identity headers are prohibited outside development/test environments. Use standard Bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Development / Test environment header resolution
    token_val = auth_creds.credentials.strip() if (auth_creds and auth_creds.credentials) else None
    user_identifier = token_val or (x_user_id or x_user_email if is_dev_allowed else None)

    if not user_identifier and not x_user_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try parsing identifier as UUID
    user_uuid: uuid.UUID | None = None
    if user_identifier:
        try:
            user_uuid = uuid.UUID(user_identifier)
        except ValueError:
            user_uuid = None

    user: User | None = None
    if user_uuid:
        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

    if not user and user_identifier:
        # Try matching by email
        candidates = [user_identifier]
        if "@" not in user_identifier:
            candidates.append(f"{user_identifier}@nerlink.internal")
        if x_user_role:
            candidates.append(f"{x_user_role}_{user_identifier[:8]}@nerlink.internal")
            candidates.append(f"{x_user_role}@nerlink.internal")

        result = await session.execute(select(User).where(User.email.in_(candidates)))
        user = result.scalars().first()

    # If user not found in DB, auto-provision dev/test user if role is present
    if not user:
        role = x_user_role or (token_val if token_val in ["admin", "dispatcher", "field_officer", "driver", "ml_service", "service_worker"] else None)
        if role:
            identifier_str = user_identifier or f"dev_{role}"
            dev_email = identifier_str if "@" in identifier_str else f"{role}_{identifier_str[:8]}@nerlink.internal"
            existing = await session.execute(select(User).where(User.email == dev_email))
            found = existing.scalar_one_or_none()
            if found:
                if not found.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is deactivated.",
                    )
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
