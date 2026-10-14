# NER-LINK — Backend Authentication & Role-Based Access Control (RBAC) Specification

## 1. Overview & Architecture

NER-LINK implements enterprise-grade, cryptographically signed authentication and role-based access control (RBAC) designed for humanitarian logistics and accessibility management in the North Eastern Region.

Key architectural pillars:
- **Argon2id Password Hashing**: Passwords are hashed using the state-of-the-art Argon2id algorithm (time cost: 2, memory cost: 64 MB, parallelism: 2, 32-byte digest), compliant with OWASP guidelines.
- **Short-Lived Signed JWT Access Tokens**: Compact tokens containing minimal necessary claims (`sub`, `role`, `email`, `iat`, `exp`, `jti`, `token_type`, `iss="nerlink"`), signed with HMAC-SHA256 (`HS256`). Default validity: 30 minutes.
- **Stateful & Revocable Refresh Sessions**: Cryptographically high-entropy (48-byte URL-safe) refresh tokens. Persisted in PostgreSQL (`user_sessions` table) only as SHA-256 hashes (`token_hash`).
- **Single-Use Refresh Token Rotation & Replay Attack Defense**: Each refresh operation invalidates the presented token and issues a new pair. If an already-revoked refresh token is replayed, the system detects a session compromise and revokes all active sessions for that user immediately.
- **Dual Refresh Transport**: Supports both `HttpOnly`, `Secure`, `SameSite=Lax` cookies for web clients and explicit JSON payloads for native apps and API clients.
- **Zero Account Enumeration**: Authentication failures return identical generic `401 Unauthorized` responses without disclosing whether the username/email or password was invalid.
- **Strict Production Hardening**: Development identity bypass headers (`X-User-Role`, `X-User-Email`, `X-User-Id`) are strictly prohibited outside development and test environments. In production, any attempt to pass these headers results in immediate `401 Unauthorized`. Production startup fails safely if insecure bypass settings or weak JWT secret keys are detected.

---

## 2. Authentication & Session Endpoints

### 2.1 Login: `POST /api/v1/auth/login`

Authenticates credentials, updates `last_login_at`, persists a new session record, sets an HttpOnly cookie, and returns access/refresh tokens.

**Request Payload:**
```json
{
  "email": "officer.borah@nerlink.org",
  "password": "SecurePassword123!"
}
```
*(Alternatively, `"username_or_email"` is accepted for flexible UI integration).*

**Success Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "a1b2c3d4e5f6...",
  "user": {
    "id": "e2a1883b-b573-4ab4-9600-236ffc5cc2e1",
    "email": "officer.borah@nerlink.org",
    "full_name": "Field Officer Borah",
    "role": "field_officer",
    "preferred_language": "en",
    "is_active": true,
    "last_login_at": "2026-10-14T16:30:00Z",
    "created_at": "2026-10-14T10:00:00Z",
    "updated_at": "2026-10-14T16:30:00Z"
  }
}
```
**Response Headers:**
- `Set-Cookie: rx_refresh_token=a1b2c3d4e5f6...; Path=/api/v1/auth; HttpOnly; SameSite=Lax; Max-Age=604800`

**Failure Responses:**
- `401 Unauthorized`: `{"detail": "Invalid username/email or password."}`
- `401 Unauthorized`: `{"detail": "Account is inactive or suspended."}`
- `429 Too Many Requests`: `{"detail": "Too many failed login attempts. Please wait 5 minutes."}`

---

### 2.2 Token Refresh: `POST /api/v1/auth/refresh`

Rotates the refresh token and issues a fresh access token. The refresh token can be delivered via the `rx_refresh_token` cookie or the request JSON body.

**Request Payload (optional if cookie is present):**
```json
{
  "refresh_token": "a1b2c3d4e5f6..."
}
```

**Success Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "f7g8h9i0j1k2...",
  "user": { ... }
}
```

**Security Invalidation Semantics:**
- If the token is valid and unrevoked, it is marked `is_revoked = True` and replaced with the new token.
- If an already revoked token is submitted, all active sessions for the user are immediately revoked, returning `401 Unauthorized: Refresh token was revoked. All active sessions have been invalidated due to potential reuse.`

---

### 2.3 Logout: `POST /api/v1/auth/logout`

Revokes the active session and clears the refresh cookie.

**Request Payload (optional if cookie is present):**
```json
{
  "refresh_token": "f7g8h9i0j1k2..."
}
```
**Headers:**
- `Authorization: Bearer <access_token>`

**Response (`200 OK`):**
```json
{
  "message": "Logged out successfully. Session revoked."
}
```
**Response Headers:**
- `Set-Cookie: rx_refresh_token=; Path=/api/v1/auth; Max-Age=0`

---

### 2.4 Authenticated Identity: `GET /api/v1/auth/me`

Returns the authenticated user's safe profile, authoritative DB role, and active status. Never returns password hashes or session tokens.

**Headers:**
- `Authorization: Bearer <access_token>`

**Response (`200 OK`):**
```json
{
  "id": "e2a1883b-b573-4ab4-9600-236ffc5cc2e1",
  "email": "officer.borah@nerlink.org",
  "full_name": "Field Officer Borah",
  "role": "field_officer",
  "preferred_language": "en",
  "is_active": true,
  "last_login_at": "2026-10-14T16:30:00Z",
  "created_at": "2026-10-14T10:00:00Z",
  "updated_at": "2026-10-14T16:30:00Z"
}
```

---

## 3. Administrative User Management: `/api/v1/users`

Only authenticated users with the `admin` role are permitted to create users, list user accounts, alter roles, toggle active status, or initiate administrator-controlled password resets.

- `POST /api/v1/users`: Create user with assigned role (`admin`, `dispatcher`, `field_officer`, `driver`, `ml_service`, `service_worker`). Hashes password with Argon2id.
- `GET /api/v1/users`: Paginated listing of platform users. Filters by `role`, `is_active`, `search`. Never returns password hashes.
- `GET /api/v1/users/{id}`: Retrieve single user profile.
- `PATCH /api/v1/users/{id}`: Modify user attributes (`role`, `is_active`, `full_name`, `preferred_language`). If `is_active` is toggled to `False`, all active sessions for that user are revoked in PostgreSQL immediately.
- `POST /api/v1/users/{id}/reset-password`: Sets a new temporary password and revokes all active sessions.

---

## 4. Role-Based Access Control (RBAC) Permission Matrix

| Resource / Endpoint | Method | Admin | Dispatcher | Field Officer | Driver | ML Service | Anonymous / Public |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Health Checks** (`/health`, `/health/ready`) | `GET` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Public |
| **GIS Road Network** (`/roads`, `/roads/geojson`, `/roads/{id}`) | `GET` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Public Basemap |
| **Auth Login / Refresh** (`/auth/login`, `/auth/refresh`) | `POST` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Public Credential |
| **Auth Profile / Logout** (`/auth/me`, `/auth/logout`) | `GET/POST` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 401 |
| **User Administration** (`/users`, `/users/{id}`, `/users/...`) | `GET/POST/PATCH` | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Submit Incident** (`/incidents`) | `POST` | ✅ | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 401 |
| **Review / Triage Incident** (`/incidents/{id}/review`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Confirm Incident** (`/incidents/{id}/confirm`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Reject / Resolve Incident** (`/incidents/{id}/reject`, `resolve`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Upload Evidence** (`/evidence/upload`) | `POST` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 401 |
| **List / Detail Evidence** (`/evidence`, `/evidence/{id}`) | `GET` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 401 |
| **Download Raw Evidence** (`/evidence/{id}/download`) | `GET` | ✅ | ✅ | ✅ | ❌ 403 | ✅ | ❌ 401 |
| **Fleet Registration / Update** (`/vehicles`, `/vehicles/{id}`) | `POST/PATCH` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Vehicle Telemetry Ingestion** (`/vehicles/{id}/location`) | `POST` | ✅ | ✅ | ❌ 403 | ✅ (Own vehicle only) | ❌ 403 | ❌ 401 |
| **Vehicle Telemetry History** (`/vehicles/{id}/locations`) | `GET` | ✅ | ✅ | ❌ 403 | ✅ (Own vehicle only) | ❌ 403 | ❌ 401 |
| **Delivery Creation & Assignment** (`/deliveries`, `/deliveries/{id}`) | `POST/PATCH` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Trip Creation & Assignment** (`/trips`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **List / View Trips** (`/trips`, `/trips/{id}`) | `GET` | ✅ | ✅ | ❌ 403 | ✅ (Own trip only) | ❌ 403 | ❌ 401 |
| **Trip Lifecycle** (`/trips/{id}/start`, `pause`, `complete`) | `POST` | ✅ | ✅ | ❌ 403 | ✅ (Own trip only) | ❌ 403 | ❌ 401 |
| **Trip Cancellation & Reroute** (`/trips/{id}/cancel`, `reroute`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **ML Pending Evidence Queue** (`/ml/evidence/pending`) | `GET` | ✅ | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 401 |
| **ML Evidence Claim & Ingest Result** (`/ml/evidence/{id}/claim`, `result`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 401 |
| **Weather & Traffic Aggregation** (`/weather/...`, `/traffic/...`) | `GET/POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Satellite Imagery Ingestion** (`/satellite/...`) | `POST` | ✅ | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 401 |

---

## 5. Object-Level Authorization Rules

In addition to coarse role checks, endpoints enforce fine-grained ownership and assignment:
1. **Driver Trip Scoping**: When a user with the `driver` role accesses `GET /trips/{id}` or `POST /trips/{id}/start|pause|resume|complete`, the trip must be assigned to that driver (`trip.driver_id == current_user.id`). Attempting to view or modify another driver's assigned trip returns `403 Forbidden`.
2. **Driver Telemetry Scoping**: When a driver calls `GET /vehicles/{id}/locations` or `POST /vehicles/{id}/location`, the vehicle must be assigned to that driver (`vehicle.assigned_driver_id == current_user.id`). Ingesting or viewing telemetry for another driver's vehicle returns `403 Forbidden`.
3. **Deactivated User Immediate Invalidation**: Deactivated user accounts (`is_active = False`) are rejected on every request with `403 Forbidden: Account is deactivated`, regardless of whether an unexpired access token exists.

---

## 6. Development Bypass vs Production Hardening

### Local Development / Testing Mode
- Enabled when `APP_ENV` is set to `development` or `test` and `ALLOW_DEV_AUTH_HEADERS=True`.
- Development headers `X-User-Role`, `X-User-Email`, and `X-User-Id` are accepted by `get_current_user` to facilitate fast testing and automated integration suites.
- If a user sends a valid Bearer JWT token, the JWT takes absolute precedence; development headers cannot override an authenticated identity.

### Production Mode
- In production (`APP_ENV=production`), `ALLOW_DEV_AUTH_HEADERS` must be `False`.
- If `ALLOW_DEV_AUTH_HEADERS=True` is configured in production, the application fails to start immediately with `ValueError: ALLOW_DEV_AUTH_HEADERS cannot be True in production environment.`
- Any incoming request carrying `X-User-Role`, `X-User-Email`, or `X-User-Id` in production is rejected with `401 Unauthorized: Development identity headers are prohibited outside development/test environments. Use standard Bearer token.`
- `JWT_SECRET_KEY` in production must be an explicit, strong secret of at least 32 characters; default placeholder strings cause immediate startup failure.

---

## 7. Copy-Paste CLI / Curl Examples

### 1. Provision a New Dispatcher User (as Admin)
```bash
curl -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dispatcher.kalita@nerlink.org",
    "full_name": "Pranab Kalita",
    "role": "dispatcher",
    "password": "SecurePassword123!"
  }'
```

### 2. Login with Credentials
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dispatcher.kalita@nerlink.org",
    "password": "SecurePassword123!"
  }'
```
*Response outputs `access_token` and `refresh_token`, and sets cookie.*

### 3. Verify Authenticated Profile (`/api/v1/auth/me`)
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 4. Perform a Permitted Action (Create a Delivery as Dispatcher)
```bash
curl -X POST "http://localhost:8000/api/v1/deliveries" \
  -H "Authorization: Bearer <DISPATCHER_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_code": "DEL-MED-0092",
    "cargo_type": "MEDICINE",
    "priority": "HIGH",
    "origin_address": "Guwahati Central Depot",
    "origin_lat": 26.14365,
    "origin_lon": 91.74172,
    "destination_address": "Tawang Civil Hospital",
    "destination_lat": 27.5862,
    "destination_lon": 91.8674
  }'
```

### 5. Demonstrate Forbidden Action (Dispatcher Attempting Admin User Creation)
```bash
curl -i -X POST "http://localhost:8000/api/v1/users" \
  -H "Authorization: Bearer <DISPATCHER_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "intruder@nerlink.org",
    "full_name": "Intruder",
    "role": "admin",
    "password": "HackerPassword123!"
  }'
```
*Returns `HTTP/1.1 403 Forbidden`: `{"detail": "Forbidden: role 'dispatcher' lacks permission for this action. Allowed: ['admin']"}`*

### 6. Refresh Access Token & Rotate Refresh Session
```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<CURRENT_REFRESH_TOKEN>"
  }'
```

### 7. Logout and Revoke Session
```bash
curl -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<CURRENT_REFRESH_TOKEN>"
  }'
```
