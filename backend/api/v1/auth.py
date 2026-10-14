"""Authentication lifecycle API endpoints (Login, Refresh, Logout, Me)."""

from typing import Annotated
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user
from backend.config import get_settings
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """
    Authenticates user credentials and issues a signed JWT access token and revocable refresh token.
    Refresh token is securely placed in an HttpOnly cookie and also provided in the response body.
    """
    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    token_resp, raw_refresh = await service.authenticate_user(
        credentials=payload,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # Attach HttpOnly, Secure refresh cookie
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return token_resp


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    payload: RefreshTokenRequest | None = None,
) -> TokenResponse:
    """
    Refreshes an access token using a valid refresh token from an HttpOnly cookie or request body.
    Implements single-use token rotation: the previous refresh token is immediately invalidated.
    """
    cookie_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    body_token = payload.refresh_token if payload and payload.refresh_token else None
    raw_refresh = body_token or cookie_token

    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token. Provide via cookie or request body.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    token_resp, new_raw_refresh = await service.refresh_session(
        raw_refresh_token=raw_refresh,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # Update HttpOnly refresh cookie with rotated token
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=new_raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return token_resp


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    payload: LogoutRequest | None = None,
) -> dict[str, str]:
    """
    Revokes the current refresh session and clears the authentication cookie.
    """
    cookie_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    body_token = payload.refresh_token if payload and payload.refresh_token else None
    raw_refresh = body_token or cookie_token

    service = AuthService(session)
    await service.logout_session(raw_refresh_token=raw_refresh)

    # Clear refresh cookie
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
    )

    return {"status": "ok", "message": "Successfully logged out and session revoked."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Returns the authenticated user's profile and assigned role.
    Rejects deactivated accounts and invalid access tokens.
    """
    return UserResponse.model_validate(current_user)
