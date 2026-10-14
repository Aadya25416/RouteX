"""Comprehensive Authentication, Session Lifecycle, and RBAC Permission Matrix Tests."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
import jwt
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.crypto import create_access_token, hash_password, verify_password
from backend.config import Settings, get_settings
from backend.models.logistics import Trip, Vehicle
from backend.models.users import User, UserSession


@pytest.fixture
def auth_settings() -> Settings:
    return get_settings()


# ============================================================================
# 1. Password Hashing and Crypto Unit Tests
# ============================================================================

def test_argon2id_password_hashing():
    raw = "SuperSecret_P@ssw0rd_2026!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password(raw, None) is False


def test_jwt_access_token_creation_and_claims(auth_settings: Settings):
    uid = uuid.uuid4()
    token = create_access_token(user_id=uid, role="dispatcher", email="test_disp@nerlink.org")
    assert isinstance(token, str)

    payload = jwt.decode(
        token,
        auth_settings.JWT_SECRET_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
        issuer="nerlink",
        options={"require": ["sub", "exp", "iat", "role"]},
    )
    assert payload["sub"] == str(uid)
    assert payload["role"] == "dispatcher"
    assert payload["email"] == "test_disp@nerlink.org"
    assert payload["token_type"] == "access"
    assert payload["exp"] > payload["iat"]


# ============================================================================
# 2. Login, Credential Verification, and Generic Failure Tests
# ============================================================================

@pytest.mark.asyncio
async def test_login_success_and_cookie_issuance(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies successful login issues signed JWT, sets HttpOnly refresh cookie, and creates session."""
    raw_pass = "SecurePass123!"
    user = User(
        id=uuid.uuid4(),
        email=f"login_success_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Valid Officer",
        role="field_officer",
        hashed_password=hash_password(raw_pass),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user.email, "password": raw_pass},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800
    assert "refresh_token" in data
    assert data["user"]["id"] == str(user.id)
    assert data["user"]["email"] == user.email
    assert data["user"]["role"] == "field_officer"
    assert "hashed_password" not in data["user"]
    assert "password" not in data["user"]

    # Verify HttpOnly cookie
    assert "rx_refresh_token" in res.cookies
    assert res.cookies["rx_refresh_token"] == data["refresh_token"]

    # Verify session persisted in DB
    sess_res = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = sess_res.scalar_one_or_none()
    assert session is not None
    assert session.is_revoked is False


@pytest.mark.asyncio
async def test_login_invalid_password_returns_generic_401(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that wrong password returns generic 401 without account leakage."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_wrongpass_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Test User",
        role="dispatcher",
        hashed_password=hash_password("CorrectPass!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user.email, "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username/email or password."


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_identical_generic_401(
    async_client: AsyncClient,
):
    """Verifies nonexistent username returns exact same message to prevent username enumeration."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "nonexistent_ghost@nerlink.org", "password": "AnyPassword123!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username/email or password."


@pytest.mark.asyncio
async def test_login_deactivated_user_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies deactivated user account is rejected on login."""
    raw_pass = "DeactivatedPass123!"
    user = User(
        id=uuid.uuid4(),
        email=f"deactivated_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Deactivated Officer",
        role="field_officer",
        hashed_password=hash_password(raw_pass),
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user.email, "password": raw_pass},
    )
    assert res.status_code == 401
    assert "inactive or suspended" in res.json()["detail"].lower()


# ============================================================================
# 3. /api/v1/auth/me Endpoint Tests
# ============================================================================

@pytest.mark.asyncio
async def test_auth_me_returns_safe_user_profile(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies /api/v1/auth/me returns safe profile without leaking password hash."""
    user = User(
        id=uuid.uuid4(),
        email=f"profile_user_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Profile User",
        role="driver",
        hashed_password=hash_password("Secret123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(user.id, user.role, user.email)
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["role"] == "driver"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_auth_me_rejects_expired_and_tampered_jwt(
    async_client: AsyncClient,
    auth_settings: Settings,
):
    """Verifies expired or tampered JWT access token is rejected with 401."""
    # 1. Expired JWT
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "email": "expired@nerlink.org",
        "token_type": "access",
        "iss": "nerlink",
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, auth_settings.JWT_SECRET_KEY, algorithm="HS256")
    res1 = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res1.status_code == 401
    assert "expired" in res1.json()["detail"].lower()

    # 2. Tampered JWT with invalid signature
    tampered_token = expired_token[:-4] + "AAAA"
    res2 = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res2.status_code == 401


# ============================================================================
# 4. Refresh Token Lifecycle, Rotation, and Replay Detection
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies token refresh returns a new token pair and rotates the refresh token."""
    raw_pass = "RotationPass123!"
    user = User(
        id=uuid.uuid4(),
        email=f"refresh_rot_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Rotation Tester",
        role="dispatcher",
        hashed_password=hash_password(raw_pass),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # 1. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user.email, "password": raw_pass},
    )
    refresh_token_1 = login_res.json()["refresh_token"]

    # 2. Refresh session using token in JSON body
    ref_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    assert "access_token" in ref_data
    refresh_token_2 = ref_data["refresh_token"]
    assert refresh_token_2 != refresh_token_1

    # 3. Attempting to REUSE rotated refresh_token_1 triggers replay detection and revocation
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert replay_res.status_code == 401
    assert "revoked" in replay_res.json()["detail"].lower()

    # 4. Verify all sessions for this user were revoked due to detected replay attack
    ref2_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert ref2_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_session(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies logout marks session revoked and clears cookie."""
    raw_pass = "LogoutPass123!"
    user = User(
        id=uuid.uuid4(),
        email=f"logout_user_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Logout User",
        role="driver",
        hashed_password=hash_password(raw_pass),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user.email, "password": raw_pass},
    )
    ref_token = login_res.json()["refresh_token"]
    access_token = login_res.json()["access_token"]

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": ref_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_res.status_code == 200

    # Attempt to use refresh token after logout -> 401
    ref_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ref_token},
    )
    assert ref_res.status_code == 401


# ============================================================================
# 5. Administrative User Management & Privilege Separation
# ============================================================================

@pytest.mark.asyncio
async def test_admin_user_crud_and_privilege_enforcement(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that only admins can create, deactivate, and reset passwords for users."""
    # Create Admin
    admin_user = User(
        id=uuid.uuid4(),
        email=f"master_admin_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Master Admin",
        role="admin",
        hashed_password=hash_password("AdminPass123!"),
        is_active=True,
    )
    # Create Field Officer
    officer_user = User(
        id=uuid.uuid4(),
        email=f"regular_officer_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Regular Officer",
        role="field_officer",
        hashed_password=hash_password("OfficerPass123!"),
        is_active=True,
    )
    db_session.add_all([admin_user, officer_user])
    await db_session.commit()

    admin_token = create_access_token(admin_user.id, admin_user.role, admin_user.email)
    officer_token = create_access_token(officer_user.id, officer_user.role, officer_user.email)

    # 1. Field officer CANNOT create users (403 Forbidden)
    create_payload = {
        "email": f"new_driver_{uuid.uuid4().hex[:6]}@nerlink.org",
        "full_name": "New Driver",
        "role": "driver",
        "password": "InitialPass123!",
    }
    denied_res = await async_client.post(
        "/api/v1/users",
        json=create_payload,
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert denied_res.status_code == 403

    # 2. Admin CAN create a user
    create_res = await async_client.post(
        "/api/v1/users",
        json=create_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_res.status_code == 201
    created_user = create_res.json()
    new_user_id = created_user["id"]
    assert created_user["role"] == "driver"
    assert "password" not in created_user
    assert "hashed_password" not in created_user

    # 3. Admin can list users
    list_res = await async_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 4. Admin deactivates user account
    deactivate_res = await async_client.patch(
        f"/api/v1/users/{new_user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivate_res.status_code == 200
    assert deactivate_res.json()["is_active"] is False

    # 5. Admin resets password
    reset_res = await async_client.post(
        f"/api/v1/users/{new_user_id}/reset-password",
        json={"new_password": "NewResetPassword123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["id"] == str(new_user_id)
    assert "hashed_password" not in reset_res.json()


# ============================================================================
# 6. Object-Level Authorization Tests
# ============================================================================

@pytest.mark.asyncio
async def test_driver_cannot_access_another_driver_trip(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that a driver cannot view or manipulate another driver's trip."""
    driver_1 = User(
        id=uuid.uuid4(),
        email=f"driver1_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Driver One",
        role="driver",
        is_active=True,
    )
    driver_2 = User(
        id=uuid.uuid4(),
        email=f"driver2_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Driver Two",
        role="driver",
        is_active=True,
    )
    vehicle = Vehicle(
        id=uuid.uuid4(),
        registration_number=f"TRK-{uuid.uuid4().hex[:6].upper()}",
        status="ASSIGNED",
        is_active=True,
    )
    trip = Trip(
        id=uuid.uuid4(),
        vehicle_id=vehicle.id,
        driver_id=driver_1.id,  # Assigned strictly to driver 1
        status="PLANNED",
    )
    db_session.add_all([driver_1, driver_2, vehicle, trip])
    await db_session.commit()

    driver1_token = create_access_token(driver_1.id, driver_1.role, driver_1.email)
    driver2_token = create_access_token(driver_2.id, driver_2.role, driver_2.email)

    # Driver 1 can view trip
    res1 = await async_client.get(
        f"/api/v1/trips/{trip.id}",
        headers={"Authorization": f"Bearer {driver1_token}"},
    )
    assert res1.status_code == 200

    # Driver 2 attempting to view Driver 1's trip is forbidden (403)
    res2 = await async_client.get(
        f"/api/v1/trips/{trip.id}",
        headers={"Authorization": f"Bearer {driver2_token}"},
    )
    assert res2.status_code == 403
    assert "another driver" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_driver_cannot_access_another_driver_vehicle_telemetry(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that a driver cannot access vehicle telemetry assigned to another driver."""
    driver_1 = User(
        id=uuid.uuid4(),
        email=f"driver_alpha_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Driver Alpha",
        role="driver",
        is_active=True,
    )
    driver_2 = User(
        id=uuid.uuid4(),
        email=f"driver_beta_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Driver Beta",
        role="driver",
        is_active=True,
    )
    vehicle = Vehicle(
        id=uuid.uuid4(),
        registration_number=f"TRK-{uuid.uuid4().hex[:6].upper()}",
        status="ASSIGNED",
        is_active=True,
        assigned_driver_id=driver_1.id,  # Assigned to driver 1
    )
    db_session.add_all([driver_1, driver_2, vehicle])
    await db_session.commit()

    driver2_token = create_access_token(driver_2.id, driver_2.role, driver_2.email)

    # Driver 2 accessing vehicle assigned to Driver 1 is forbidden (403)
    res = await async_client.get(
        f"/api/v1/vehicles/{vehicle.id}/locations",
        headers={"Authorization": f"Bearer {driver2_token}"},
    )
    assert res.status_code == 403
    assert "another driver" in res.json()["detail"].lower()


# ============================================================================
# 7. Production Hardening & Dev Header Rejection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_production_mode_strictly_rejects_dev_headers(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    auth_settings: Settings,
):
    """
    Verifies that when APP_ENV is 'production' (or ALLOW_DEV_AUTH_HEADERS is False),
    incoming X-User-Role / X-User-Email headers are rejected with 401 Unauthorized.
    """
    monkeypatch.setattr(auth_settings, "ALLOW_DEV_AUTH_HEADERS", False)

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"X-User-Role": "admin", "X-User-Email": "admin_hacker@nerlink.org"},
    )
    assert res.status_code == 401
    assert "prohibited outside development" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dev_header_cannot_override_valid_bearer_token(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that even if dev headers are sent alongside a Bearer token,
    the Bearer token identity always takes precedence and cannot be escalated.
    """
    driver_user = User(
        id=uuid.uuid4(),
        email=f"driver_humble_{uuid.uuid4().hex[:6]}@nerlink.org",
        full_name="Humble Driver",
        role="driver",
        is_active=True,
    )
    db_session.add(driver_user)
    await db_session.commit()

    driver_token = create_access_token(driver_user.id, driver_user.role, driver_user.email)

    # Send driver JWT token with deceptive X-User-Role: admin header
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {driver_token}",
            "X-User-Role": "admin",
            "X-User-Email": "super_admin@nerlink.org",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "driver"
    assert data["email"] == driver_user.email
    assert data["id"] == str(driver_user.id)


def test_production_settings_validation_fails_safely():
    """Verifies that attempting to run production with ALLOW_DEV_AUTH_HEADERS or weak secret fails."""
    with pytest.raises(ValueError, match="ALLOW_DEV_AUTH_HEADERS cannot be True in production"):
        Settings(
            APP_ENV="production",
            ALLOW_DEV_AUTH_HEADERS=True,
            JWT_SECRET_KEY="a" * 32,
        )

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            APP_ENV="production",
            ALLOW_DEV_AUTH_HEADERS=False,
            JWT_SECRET_KEY="short_weak_secret",
        )


# ============================================================================
# 8. Complete RBAC Role Permissions Matrix
# ============================================================================

@pytest.mark.asyncio
async def test_rbac_permission_matrix_across_roles(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Tests the complete permission matrix across all key roles:
    - Admin: can manage users, create vehicles, review incidents.
    - Dispatcher: can create vehicles/deliveries, cannot manage users.
    - Field Officer: can create incidents/evidence, cannot confirm incidents or manage users.
    - Driver: cannot manage users, cannot create deliveries or confirm incidents.
    - ML Service: can access ML evidence endpoints, cannot access user admin or logistics.
    """
    # 1. Setup users in DB and generate signed tokens for each role
    admin_user = User(id=uuid.uuid4(), email=f"admin_mat_{uuid.uuid4().hex[:6]}@nerlink.org", full_name="Admin Matrix", role="admin", is_active=True)
    disp_user = User(id=uuid.uuid4(), email=f"disp_mat_{uuid.uuid4().hex[:6]}@nerlink.org", full_name="Disp Matrix", role="dispatcher", is_active=True)
    officer_user = User(id=uuid.uuid4(), email=f"officer_mat_{uuid.uuid4().hex[:6]}@nerlink.org", full_name="Officer Matrix", role="field_officer", is_active=True)
    driver_user = User(id=uuid.uuid4(), email=f"driver_mat_{uuid.uuid4().hex[:6]}@nerlink.org", full_name="Driver Matrix", role="driver", is_active=True)
    ml_user = User(id=uuid.uuid4(), email=f"ml_mat_{uuid.uuid4().hex[:6]}@nerlink.org", full_name="ML Matrix", role="ml_service", is_active=True)
    db_session.add_all([admin_user, disp_user, officer_user, driver_user, ml_user])
    await db_session.commit()

    admin_token = create_access_token(admin_user.id, admin_user.role, admin_user.email)
    dispatcher_token = create_access_token(disp_user.id, disp_user.role, disp_user.email)
    officer_token = create_access_token(officer_user.id, officer_user.role, officer_user.email)
    driver_token = create_access_token(driver_user.id, driver_user.role, driver_user.email)
    ml_token = create_access_token(ml_user.id, ml_user.role, ml_user.email)

    # A. User Management (/api/v1/users) -> Admin ONLY
    user_payload = {
        "email": f"matrix_test_{uuid.uuid4().hex[:6]}@nerlink.org",
        "full_name": "Matrix Tester",
        "role": "driver",
        "password": "Password123!",
    }
    assert (await async_client.post("/api/v1/users", json=user_payload, headers={"Authorization": f"Bearer {admin_token}"})).status_code == 201
    assert (await async_client.post("/api/v1/users", json=user_payload, headers={"Authorization": f"Bearer {dispatcher_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/users", json=user_payload, headers={"Authorization": f"Bearer {officer_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/users", json=user_payload, headers={"Authorization": f"Bearer {driver_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/users", json=user_payload, headers={"Authorization": f"Bearer {ml_token}"})).status_code == 403

    # B. Vehicle Management (/api/v1/vehicles) -> Admin and Dispatcher ONLY
    veh_payload = {
        "registration_number": f"MX-{uuid.uuid4().hex[:6].upper()}",
        "vehicle_type": "truck",
        "status": "AVAILABLE",
    }
    assert (await async_client.post("/api/v1/vehicles", json=veh_payload, headers={"Authorization": f"Bearer {dispatcher_token}"})).status_code == 201
    veh_payload["registration_number"] = f"MX-{uuid.uuid4().hex[:6].upper()}"
    assert (await async_client.post("/api/v1/vehicles", json=veh_payload, headers={"Authorization": f"Bearer {officer_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/vehicles", json=veh_payload, headers={"Authorization": f"Bearer {driver_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/vehicles", json=veh_payload, headers={"Authorization": f"Bearer {ml_token}"})).status_code == 403

    # C. Delivery Management (/api/v1/deliveries) -> Admin and Dispatcher ONLY
    deliv_payload = {
        "tracking_code": f"DEL-{uuid.uuid4().hex[:6].upper()}",
        "cargo_type": "FOOD",
        "origin_address": "Guwahati Depot",
        "origin_lat": 26.14365,
        "origin_lon": 91.74172,
        "destination_address": "Tezpur Hub",
        "destination_lat": 26.65,
        "destination_lon": 92.79,
    }
    assert (await async_client.post("/api/v1/deliveries", json=deliv_payload, headers={"Authorization": f"Bearer {dispatcher_token}"})).status_code == 201
    deliv_payload["tracking_code"] = f"DEL-{uuid.uuid4().hex[:6].upper()}"
    assert (await async_client.post("/api/v1/deliveries", json=deliv_payload, headers={"Authorization": f"Bearer {officer_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/deliveries", json=deliv_payload, headers={"Authorization": f"Bearer {driver_token}"})).status_code == 403
    assert (await async_client.post("/api/v1/deliveries", json=deliv_payload, headers={"Authorization": f"Bearer {ml_token}"})).status_code == 403

    # D. Incident Review/Action (/api/v1/incidents/{id}/review) -> Admin and Dispatcher ONLY
    inc_payload = {
        "incident_type": "LANDSLIDE",
        "severity": "HIGH",
        "latitude": 26.14365,
        "longitude": 91.74172,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "client_report_id": str(uuid.uuid4()),
    }
    inc_res = await async_client.post("/api/v1/incidents", json=inc_payload, headers={"Authorization": f"Bearer {officer_token}"})
    assert inc_res.status_code == 201
    inc_id = inc_res.json()["id"]

    # Field officer cannot review/triage incidents (403)
    assert (await async_client.post(f"/api/v1/incidents/{inc_id}/review", json={"review_notes": "Attempt by officer"}, headers={"Authorization": f"Bearer {officer_token}"})).status_code == 403
    # Driver cannot review/triage incidents (403)
    assert (await async_client.post(f"/api/v1/incidents/{inc_id}/review", json={"review_notes": "Attempt by driver"}, headers={"Authorization": f"Bearer {driver_token}"})).status_code == 403
    # ML service cannot review/triage incidents (403)
    assert (await async_client.post(f"/api/v1/incidents/{inc_id}/review", json={"review_notes": "Attempt by ML"}, headers={"Authorization": f"Bearer {ml_token}"})).status_code == 403

    # Dispatcher CAN review/triage incidents (200)
    assert (await async_client.post(f"/api/v1/incidents/{inc_id}/review", json={"review_notes": "Reviewed by dispatcher"}, headers={"Authorization": f"Bearer {dispatcher_token}"})).status_code == 200

    # E. ML Evidence Pending Queue (/api/v1/ml/evidence/pending) -> ML Service, Dispatcher, Admin
    assert (await async_client.get("/api/v1/ml/evidence/pending", headers={"Authorization": f"Bearer {ml_token}"})).status_code == 200
    assert (await async_client.get("/api/v1/ml/evidence/pending", headers={"Authorization": f"Bearer {driver_token}"})).status_code == 403
    assert (await async_client.get("/api/v1/ml/evidence/pending", headers={"Authorization": f"Bearer {officer_token}"})).status_code == 403


# ============================================================================
# 8. Driver Self-Registration and Auth Connectivity Tests
# ============================================================================

@pytest.mark.asyncio
async def test_driver_self_registration_success_and_subsequent_login(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies public driver self-registration:
    1. Creates active driver account without administrator intervention.
    2. Hashes password using Argon2id.
    3. Allows immediate subsequent login with issued credentials.
    """
    reg_email = f"driver_selfreg_{uuid.uuid4().hex[:6]}@routex.ai"
    reg_pass = "SecureDriverPass123!"
    reg_payload = {
        "email": reg_email,
        "full_name": "Self Reg Driver",
        "password": reg_pass,
    }

    # 1. Driver self-registration
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    data = reg_res.json()
    assert data["email"] == reg_email.lower()
    assert data["full_name"] == "Self Reg Driver"
    assert data["role"] == "driver"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify user state in DB
    db_res = await db_session.execute(select(User).where(User.email == reg_email.lower()))
    driver_user = db_res.scalar_one_or_none()
    assert driver_user is not None
    assert driver_user.role == "driver"
    assert driver_user.is_active is True
    assert verify_password(reg_pass, driver_user.hashed_password) is True

    # 2. Subsequent login with newly created credentials
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": reg_email, "password": reg_pass},
    )
    assert login_res.status_code == 200, login_res.text
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["email"] == reg_email.lower()
    assert login_data["user"]["role"] == "driver"
    assert "rx_refresh_token" in login_res.cookies


@pytest.mark.asyncio
async def test_driver_self_registration_duplicate_email_rejected(
    async_client: AsyncClient,
):
    """Verifies that attempting to register an already-registered email returns 409 Conflict."""
    email = f"driver_dup_{uuid.uuid4().hex[:6]}@routex.ai"
    payload = {
        "email": email,
        "full_name": "First Driver",
        "password": "Password123!",
    }

    # First registration succeeds
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with duplicate email fails with 409 Conflict
    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409, res2.text
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_driver_self_registration_privilege_escalation_forced_to_driver(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that client cannot supply privileged roles (admin, dispatcher, field_officer, ml_service)
    during public self-registration. Role is strictly assigned by backend as 'driver'.
    """
    for privileged_role in ["admin", "dispatcher", "field_officer", "ml_service"]:
        email = f"escalate_{privileged_role}_{uuid.uuid4().hex[:6]}@routex.ai"
        payload = {
            "email": email,
            "full_name": f"Attacker {privileged_role}",
            "password": "Password123!",
            "role": privileged_role,
        }

        res = await async_client.post("/api/v1/auth/register", json=payload)
        # Backend must either reject or safely force the role to driver
        assert res.status_code in (201, 400, 403), res.text
        if res.status_code == 201:
            data = res.json()
            assert data["role"] == "driver", f"Role was not forced to driver: {data['role']}"

            # Verify in DB that role is strictly 'driver'
            db_res = await db_session.execute(select(User).where(User.email == email.lower()))
            user = db_res.scalar_one_or_none()
            assert user is not None
            assert user.role == "driver", f"DB role was not 'driver': {user.role}"


@pytest.mark.asyncio
async def test_auth_endpoints_connectivity(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that all four core authentication endpoints are wired and reachable:
    - POST /api/v1/auth/login
    - POST /api/v1/auth/refresh
    - POST /api/v1/auth/logout
    - GET /api/v1/auth/me
    """
    email = f"connect_test_{uuid.uuid4().hex[:6]}@routex.ai"
    password = "TestConnectPass123!"
    user = User(
        id=uuid.uuid4(),
        email=email.lower(),
        full_name="Connect Tester",
        role="driver",
        hashed_password=hash_password(password),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # 1. POST /api/v1/auth/login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": email, "password": password},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    # 2. GET /api/v1/auth/me (authenticated)
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email.lower()

    # 3. POST /api/v1/auth/refresh (rotate token)
    ref_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_res.status_code == 200
    new_access_token = ref_res.json()["access_token"]
    assert new_access_token != access_token

    # 4. POST /api/v1/auth/logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": ref_res.json()["refresh_token"]},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "ok"


