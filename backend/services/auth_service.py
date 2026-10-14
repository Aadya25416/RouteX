"""Authentication and User Account Domain Service."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException, status
import redis.asyncio as aioredis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.crypto import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from backend.config import get_settings
from backend.models.users import User, UserSession
from backend.schemas.auth import (
    LoginRequest,
    PasswordResetRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from backend.services.events import record_audit_log

logger = logging.getLogger(__name__)
settings = get_settings()

VALID_ROLES = {"admin", "dispatcher", "field_officer", "driver", "ml_service"}


class AuthService:
    """Manages authentication, session tracking, token rotation, and account lifecycle."""

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis | None = None):
        self.session = session
        self.redis_client = redis_client

    async def _get_redis(self) -> aioredis.Redis | None:
        if self.redis_client:
            return self.redis_client
        try:
            return aioredis.from_url(
                settings.redis_url,
                socket_connect_timeout=1.0,
                decode_responses=True,
            )
        except Exception as exc:
            logger.warning(f"Could not connect to Redis for auth rate limiting: {exc}")
            return None

    async def _check_rate_limit(self, identifier: str) -> None:
        """Enforces rate limiting on consecutive failed login attempts."""
        client = await self._get_redis()
        if not client:
            return

        key = f"auth:rate_limit:login:{identifier.lower()}"
        try:
            attempts = await client.get(key)
            if attempts and int(attempts) >= settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS:
                ttl = await client.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again in {max(ttl, 1)} seconds.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"Rate limiting check error: {exc}")
        finally:
            await client.aclose()

    async def _record_failed_attempt(self, identifier: str) -> None:
        """Increments failed attempt counter with configured TTL window."""
        client = await self._get_redis()
        if not client:
            return

        key = f"auth:rate_limit:login:{identifier.lower()}"
        try:
            val = await client.incr(key)
            if val == 1:
                await client.expire(key, settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS)
        except Exception as exc:
            logger.warning(f"Rate limiting increment error: {exc}")
        finally:
            await client.aclose()

    async def _clear_failed_attempts(self, identifier: str) -> None:
        """Clears failed login attempt counter upon successful authentication."""
        client = await self._get_redis()
        if not client:
            return

        key = f"auth:rate_limit:login:{identifier.lower()}"
        try:
            await client.delete(key)
        except Exception as exc:
            logger.warning(f"Rate limiting clear error: {exc}")
        finally:
            await client.aclose()

    async def authenticate_user(
        self,
        credentials: LoginRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[TokenResponse, str]:
        """
        Validates user credentials, verifies password via Argon2id, and issues access + refresh tokens.
        Returns:
            (TokenResponse, raw_refresh_token)
        """
        raw_identity = credentials.email or credentials.username_or_email
        if not raw_identity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email or username is required.",
            )
        normalized_email = str(raw_identity).strip().lower()
        await self._check_rate_limit(normalized_email)

        # Query user
        result = await self.session.execute(select(User).where(func.lower(User.email) == normalized_email))
        user = result.scalar_one_or_none()

        # Generic 401 to prevent account enumeration
        if not user or not user.hashed_password or not verify_password(credentials.password, user.hashed_password):
            await self._record_failed_attempt(normalized_email)
            record_audit_log(
                session=self.session,
                action="auth_login_failed",
                entity_type="user",
                entity_id=str(user.id) if user else normalized_email,
                details={"reason": "invalid_credentials", "ip": ip_address},
            )
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username/email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive or suspended.",
            )

        # Clear failed counter on success
        await self._clear_failed_attempts(normalized_email)

        now = datetime.now(timezone.utc)
        user.last_login_at = now

        # 1. Issue short-lived access token
        access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            email=user.email,
        )

        # 2. Issue rotatable refresh token
        raw_refresh, token_hash = generate_refresh_token()
        refresh_expires = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        session_record = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_expires,
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip_address[:45] if ip_address else None,
            created_at=now,
        )
        self.session.add(session_record)

        record_audit_log(
            session=self.session,
            action="auth_login_success",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            details={"ip": ip_address, "role": user.role},
        )

        await self.session.commit()
        await self.session.refresh(user)

        user_resp = UserResponse.model_validate(user)
        token_resp = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=raw_refresh,
            user=user_resp,
        )
        return token_resp, raw_refresh

    async def refresh_session(
        self,
        raw_refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[TokenResponse, str]:
        """
        Validates refresh token, detects token reuse, rotates refresh session, and issues a new access token.
        Returns:
            (TokenResponse, new_raw_refresh_token)
        """
        token_hash = hash_token(raw_refresh_token.strip())

        res = await self.session.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        session_record = res.scalar_one_or_none()

        if not session_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or unrecognized refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)

        # Token Reuse Detection (Replay Attack Protection)
        if session_record.is_revoked:
            logger.critical(
                f"SECURITY ALERT: Refresh token reuse detected for user {session_record.user_id}! "
                f"Revoking all active sessions immediately."
            )
            # Revoke all sessions for this user
            await self.revoke_all_user_sessions(session_record.user_id)
            record_audit_log(
                session=self.session,
                action="auth_token_reuse_detected",
                entity_type="user",
                entity_id=str(session_record.user_id),
                details={"ip": ip_address, "session_id": str(session_record.id)},
            )
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Compromised or already revoked token detected. All active sessions have been invalidated.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if session_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please re-authenticate.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Load user
        user = await self.session.get(User, session_record.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated or no longer exists.",
            )

        # Rotate refresh token: revoke current session
        session_record.is_revoked = True
        session_record.revoked_at = now

        # Create new rotated refresh token & session record
        new_raw_refresh, new_token_hash = generate_refresh_token()
        new_session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip_address[:45] if ip_address else None,
            created_at=now,
        )
        self.session.add(new_session)

        # Issue fresh access token
        new_access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            email=user.email,
        )

        record_audit_log(
            session=self.session,
            action="auth_token_refreshed",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            details={"ip": ip_address},
        )

        await self.session.commit()
        await self.session.refresh(user)

        user_resp = UserResponse.model_validate(user)
        token_resp = TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_raw_refresh,
            user=user_resp,
        )
        return token_resp, new_raw_refresh

    async def logout_session(self, raw_refresh_token: str | None, current_user: User | None = None) -> bool:
        """Revokes the refresh token session and records logout."""
        if not raw_refresh_token:
            return True

        token_hash = hash_token(raw_refresh_token.strip())
        res = await self.session.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        session_record = res.scalar_one_or_none()
        if session_record and not session_record.is_revoked:
            session_record.is_revoked = True
            session_record.revoked_at = datetime.now(timezone.utc)

            record_audit_log(
                session=self.session,
                action="auth_logout",
                entity_type="user",
                entity_id=str(session_record.user_id),
                actor_id=current_user.id if current_user else session_record.user_id,
                details={"session_id": str(session_record.id)},
            )
            await self.session.commit()
        return True

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revokes all active sessions for a user (e.g. on deactivation or password reset)."""
        now = datetime.now(timezone.utc)
        res = await self.session.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
        )
        active_sessions = res.scalars().all()
        for s in active_sessions:
            s.is_revoked = True
            s.revoked_at = now
        return len(active_sessions)

    # -------------------------------------------------------------
    # User Account Management
    # -------------------------------------------------------------

    async def create_user(
        self,
        payload: UserCreateRequest,
        actor: User,
    ) -> User:
        """Creates a new user account with assigned role and hashed credentials."""
        if actor.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can provision user accounts.",
            )

        normalized_email = payload.email.strip().lower()
        if payload.role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role '{payload.role}'. Must be one of: {sorted(list(VALID_ROLES))}",
            )

        # Check existing account
        existing = await self.session.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{normalized_email}' already exists.",
            )

        hashed_pw = hash_password(payload.password)

        new_user = User(
            id=uuid.uuid4(),
            email=normalized_email,
            full_name=payload.full_name.strip(),
            hashed_password=hashed_pw,
            role=payload.role,
            preferred_language=payload.preferred_language,
            is_active=True,
        )
        self.session.add(new_user)

        record_audit_log(
            session=self.session,
            action="user_created",
            entity_type="user",
            entity_id=str(new_user.id),
            actor_id=actor.id,
            details={"email": normalized_email, "role": payload.role},
        )

        await self.session.commit()
        await self.session.refresh(new_user)
        logger.info(f"Admin '{actor.email}' created user '{new_user.email}' with role '{new_user.role}'.")
        return new_user

    async def list_users(
        self,
        role: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[User]]:
        """Lists users with filtering and pagination."""
        query = select(User)
        count_query = select(func.count(User.id))

        if role:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active.is_(is_active))
            count_query = count_query.where(User.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search.strip().lower()}%"
            condition = or_(
                func.lower(User.email).like(search_pattern),
                func.lower(User.full_name).like(search_pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        total_res = await self.session.execute(count_query)
        total = total_res.scalar() or 0

        res = await self.session.execute(
            query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        users = list(res.scalars().all())
        return total, users

    async def update_user(
        self,
        user_id: uuid.UUID,
        payload: UserUpdateRequest,
        actor: User,
    ) -> User:
        """Updates user account attributes. Role and active status modifications require admin privileges."""
        target_user = await self.session.get(User, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found.",
            )

        # Permission check: Non-admins can only update their own safe profile attributes
        is_admin = actor.role == "admin"
        if not is_admin and actor.id != target_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You lack permission to modify another user's profile.",
            )

        if payload.role is not None and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can modify user roles.",
            )

        if payload.is_active is not None and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can activate or deactivate accounts.",
            )

        if payload.role is not None:
            if payload.role not in VALID_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid role '{payload.role}'.",
                )
            target_user.role = payload.role

        if payload.is_active is not None:
            target_user.is_active = payload.is_active
            if not payload.is_active:
                # Account deactivated: immediately revoke all active sessions
                revoked_count = await self.revoke_all_user_sessions(target_user.id)
                logger.info(f"User '{target_user.email}' deactivated. Revoked {revoked_count} active sessions.")

        if payload.full_name is not None:
            target_user.full_name = payload.full_name.strip()

        if payload.preferred_language is not None:
            target_user.preferred_language = payload.preferred_language

        record_audit_log(
            session=self.session,
            action="user_updated",
            entity_type="user",
            entity_id=str(target_user.id),
            actor_id=actor.id,
            details=payload.model_dump(exclude_unset=True),
        )

        await self.session.commit()
        await self.session.refresh(target_user)
        return target_user

    async def reset_password(
        self,
        user_id: uuid.UUID,
        payload: PasswordResetRequest,
        actor: User,
    ) -> User:
        """Sets a new password for an account and invalidates all active sessions."""
        target_user = await self.session.get(User, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found.",
            )

        is_admin = actor.role == "admin"
        if not is_admin and actor.id != target_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You lack permission to reset another user's password.",
            )

        target_user.hashed_password = hash_password(payload.new_password)

        # Invalidate all existing sessions so old tokens cannot be refreshed
        revoked_count = await self.revoke_all_user_sessions(target_user.id)

        record_audit_log(
            session=self.session,
            action="user_password_reset",
            entity_type="user",
            entity_id=str(target_user.id),
            actor_id=actor.id,
            details={"revoked_sessions": revoked_count},
        )

        await self.session.commit()
        await self.session.refresh(target_user)
        logger.info(f"Password reset for user '{target_user.email}'. Revoked {revoked_count} sessions.")
        return target_user
