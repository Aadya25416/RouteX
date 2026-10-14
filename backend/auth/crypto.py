"""Cryptographic, password hashing, and JWT token utilities."""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import argon2
import jwt
from fastapi import HTTPException, status

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Argon2id password hasher configured with secure OWASP parameters
password_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    type=argon2.Type.ID,
)


def hash_password(plain_password: str) -> str:
    """Hashes a plain text password using Argon2id."""
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verifies a plain text password against an Argon2id hash."""
    if not hashed_password:
        return False
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError, argon2.exceptions.InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Checks whether the password hash needs to be upgraded to current parameters."""
    return password_hasher.check_needs_rehash(hashed_password)


def hash_token(raw_token: str) -> str:
    """Generates SHA-256 digest of a refresh token for safe database persistence."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """
    Generates a high-entropy URL-safe random refresh token.
    Returns:
        (raw_token, token_hash_sha256)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def create_access_token(
    user_id: uuid.UUID,
    role: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Issues a cryptographically signed, short-lived JWT access token.
    Claims: sub, role, email, iat, exp, jti, iss, token_type.
    """
    now = datetime.now(timezone.utc)
    expire_minutes = expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expire_minutes

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "token_type": "access",
        "iss": "nerlink",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Validates signature, expiration, issuer, and structure of a JWT access token.
    Raises HTTPException(401) on invalid signature, expiration, or malformed claims.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="nerlink",
            options={"require": ["sub", "exp", "iat", "role"]},
        )
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please re-authenticate or refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        logger.warning(f"JWT verification failure: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: signature or claims invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
