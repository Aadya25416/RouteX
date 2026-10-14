"""Authentication and User Account Pydantic Schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """User credential login request payload."""
    email: EmailStr | None = None
    username_or_email: str | None = None
    password: str = Field(..., min_length=6, description="Plaintext password for verification")


class TokenResponse(BaseModel):
    """Successful authentication response containing JWT access token and user metadata."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    refresh_token: str | None = Field(None, description="Optional refresh token string for non-cookie clients")
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Token refresh payload (optional when refresh token is supplied via HttpOnly cookie)."""
    refresh_token: str | None = Field(None, description="Refresh token string")


class LogoutRequest(BaseModel):
    """Session logout request payload."""
    refresh_token: str | None = Field(None, description="Refresh token string to revoke")


class UserResponse(BaseModel):
    """Safe public user profile representation. Never exposes password hashes."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    preferred_language: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    """Administrative user provisioning request."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, description="Initial account password")
    role: str = Field("field_officer", description="Role: admin, dispatcher, field_officer, driver, ml_service")
    preferred_language: str = Field("en", min_length=2, max_length=10)


class UserUpdateRequest(BaseModel):
    """User profile update request."""
    full_name: str | None = Field(None, min_length=2, max_length=255)
    role: str | None = Field(None, description="Updated role (admin only)")
    is_active: bool | None = Field(None, description="Account active status (admin only)")
    preferred_language: str | None = Field(None, min_length=2, max_length=10)


class PasswordResetRequest(BaseModel):
    """Administrative or user password reset payload."""
    new_password: str = Field(..., min_length=8, description="New secure password")


class UserListResponse(BaseModel):
    """Paginated list of user accounts."""
    total: int
    limit: int
    offset: int
    items: list[UserResponse]


TokenResponse.model_rebuild()
