# NER-LINK — Logistics Accessibility Intelligence Platform

**Problem Statement:** SIH26002  
**Corridor (Provisional):** Guwahati–Tawang (Configurable Study Area)  
**Architecture:** Python + FastAPI, PostgreSQL 16 + PostGIS 3.4, Redis 7, SQLAlchemy 2.0, Alembic, OSMnx/NetworkX

NER-LINK provides road accessibility intelligence, disruption management, essential logistics consignment tracking, and routable road graph navigation for the North Eastern Region.

---

## 1. Prerequisites

- **Python**: `>= 3.11` (Python 3.12 recommended)
- **uv**: Fast Python package manager ([install instructions](https://github.com/astral-sh/uv))
- **Docker & Docker Compose**: Docker Engine v24+ and Compose v2+

---

## 2. Quickstart with Docker Compose

To start the entire platform stack (PostgreSQL with PostGIS, Redis, and FastAPI):

```bash
# 1. Create your local .env configuration from the template
cp .env.example .env

# 2. Build and start containers in the background
docker compose up -d --build

# 3. Check container status
docker compose ps

# 4. View application logs
docker compose logs -f api
```

The services will be exposed at:
- **FastAPI API & OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Live**: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- **Health Ready**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)
- **PostgreSQL / PostGIS**: `localhost:55432` (avoids conflict with default 5432)
- **Redis**: `localhost:56379` (avoids conflict with default 6379)

---

## 3. Local Development Setup (Virtual Environment)

If developing outside Docker containers:

```bash
# 1. Start database and Redis services only
docker compose up -d db redis

# 2. Create virtual environment using uv
uv venv .venv --python 3.12
source .venv/bin/activate

# 3. Install dependencies in editable mode including dev/test packages
uv pip install -e ".[dev]"

# 4. Run database migrations
uv run alembic upgrade head

# 5. Start development API server
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4. Running Tests

The test suite runs with `pytest` using the project's virtual environment.

### Option A: Using `uv run` from the project root (Recommended)

```bash
# Run all tests
uv run pytest -v

# Run with verbose output and test names
uv run pytest -v -s

# Run a specific test module
uv run pytest tests/test_roads_api.py -v
```

### Option B: From an activated virtual environment

```bash
# Activate virtual environment
source .venv/bin/activate

# Run pytest from project root
pytest -v
```

> **Note on `ModuleNotFoundError`**: Running `pytest` directly without activating `.venv` or without `uv run` invokes your machine's global Python interpreter where dependencies like `redis` or `geoalchemy2` are not installed. Always use `uv run pytest` or activate `.venv`.

---

## 5. Database Migrations

Alembic manages schema migrations with PostGIS spatial type compatibility:

```bash
# Apply pending migrations
uv run alembic upgrade head

# Generate a new migration revision
uv run alembic revision --autogenerate -m "Add new column or model"

# Rollback one migration
uv run alembic downgrade -1
```

---

## 6. OpenStreetMap Road Network Ingestion

NER-LINK includes a directed graph importer that preserves road topology, one-way constraints, length, and canonical segment IDs. Operational statuses initialize to `UNKNOWN` per PRD requirements.

### Import a Configurable Bounding Box

```bash
# Example: Import Guwahati core demo area
uv run python -m backend.scripts.import_osm \
  --south 26.14 \
  --west 91.73 \
  --north 26.16 \
  --east 91.75 \
  --corridor-name "Guwahati-Core"

# Example: Import with GraphML file caching for offline runs
uv run python -m backend.scripts.import_osm \
  --south 26.10 \
  --west 91.50 \
  --north 27.70 \
  --east 92.80 \
  --corridor-name "Guwahati-Tawang" \
  --cache-file data/osm/guwahati_tawang.graphml
```

### Validate Graph Topology & Routability

Run the diagnostic validation script to verify graph connectivity and Dijkstra routing:

```bash
uv run python -m backend.scripts.validate_graph
```

---

## 7. API Reference (Phase 1 Baseline)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service overview, corridor bounding box, and OSM attribution |
| `GET` | `/health/live` | Liveness check |
| `GET` | `/health/ready` | Readiness check verifying PostGIS & Redis connectivity |
| `GET` | `/api/v1/roads` | Bounded road segment listing with pagination and bbox filter |
| `GET` | `/api/v1/roads/{id}` | Single canonical road segment details and LineString coordinates |
| `GET` | `/api/v1/roads/geojson` | GeoJSON FeatureCollection bounded by map coordinates |
| `POST` | `/api/v1/incidents` | Create geotagged field incident with PostGIS road candidate matching |
| `GET` | `/api/v1/incidents` | List incidents with pagination and type/severity/status/bbox filters |
| `GET` | `/api/v1/incidents/{id}` | Retrieve single incident details, road associations, and evidence metadata |
| `POST` | `/api/v1/incidents/{id}/review` | Dispatcher/Admin begins official review (`UNDER_REVIEW`) |
| `POST` | `/api/v1/incidents/{id}/confirm` | Dispatcher/Admin confirms incident, verifying road segments & updating operational state |
| `POST` | `/api/v1/incidents/{id}/reject` | Dispatcher/Admin rejects incident with mandatory reason |
| `POST` | `/api/v1/incidents/{id}/resolve` | Dispatcher/Admin resolves incident (retains `UNKNOWN` unless verified clearance) |
| `POST` | `/api/v1/incidents/{id}/evidence` | Upload photographic evidence with magic-byte validation |
| `GET` | `/api/v1/incidents/{id}/evidence` | List evidence metadata for an incident |
| `GET` | `/api/v1/incidents/{id}/evidence/{ref}/download` | Protected download of uploaded evidence file |

Interactive Swagger documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 8. Phase 2 — Field Incident Management Workflow

### Incident Lifecycle
```
SUBMITTED ──► UNDER_REVIEW ──► CONFIRMED ──► RESOLVED
    │                │
    ▼                ▼
 REJECTED         REJECTED
```

1. **Submission**: Authorized field officers submit geotagged reports. PostGIS (`ST_DWithin` & `ST_Distance`) identifies candidate road segments within a configurable radius (`INCIDENT_ROAD_MATCH_RADIUS_M=150.0`). Idempotency is guaranteed via `client_report_id`.
2. **Review & Confirmation**: Dispatchers/Administrators review and confirm incidents, specifying assessed impacts (`BLOCKED`, `RESTRICTED`, `AT_RISK`) per affected road segment.
3. **Road State Aggregation Rule**: When an incident is confirmed, affected road states update according to strict precedence: `BLOCKED` > `RESTRICTED` > `AT_RISK`. Resolving one incident accounts for all remaining active confirmed disruptions; if no active disruptions remain without verified clearance, status reverts to `UNKNOWN`, never erroneously `OPEN`.
4. **Evidence Storage & Protection**: Uploaded images are validated via file header magic bytes (JPEG, PNG, WebP) and size limits (15 MB), stored locally under `data/evidence/` with server-controlled filenames, and retrieved only through authenticated endpoints.
5. **Durable Events & Audit Logs**: State transitions generate immutable `audit_logs` in PostgreSQL and publish standardized events (`incident.created`, `incident.confirmed`, `incident.rejected`, `incident.resolved`, `road.status_changed`, `incident.evidence_uploaded`) to Redis Streams with error-resilient fallback.

### Verification Example Commands

```bash
# 1. Submit an incident as field officer
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -H "X-User-Role: field_officer" \
  -H "X-User-Email: officer@nerlink.org" \
  -d '{
    "incident_type": "LANDSLIDE",
    "severity": "HIGH",
    "latitude": 26.15,
    "longitude": 91.75,
    "description": "Massive landslide blocking highway",
    "observed_at": "2026-10-12T14:00:00Z",
    "client_report_id": "report_guwahati_001"
  }'

# 2. Upload evidence photograph
curl -X POST http://localhost:8000/api/v1/incidents/{INCIDENT_ID}/evidence \
  -H "X-User-Role: field_officer" \
  -H "X-User-Email: officer@nerlink.org" \
  -F "file=@photo.jpg;type=image/jpeg"

# 3. Confirm incident as dispatcher and block segment
curl -X POST http://localhost:8000/api/v1/incidents/{INCIDENT_ID}/confirm \
  -H "Content-Type: application/json" \
  -H "X-User-Role: dispatcher" \
  -H "X-User-Email: dispatcher@nerlink.org" \
  -d '{
    "review_notes": "Ground verification complete by patrol team",
    "road_impacts": [
      {"road_segment_id": "edge_4972479207_4972479335_0", "assessed_impact": "BLOCKED"}
    ]
  }'

# 4. Resolve incident
curl -X POST http://localhost:8000/api/v1/incidents/{INCIDENT_ID}/resolve \
  -H "Content-Type: application/json" \
  -H "X-User-Role: dispatcher" \
  -H "X-User-Email: dispatcher@nerlink.org" \
  -d '{
    "resolution_notes": "Debris cleared by excavator",
    "verified_clearance": false
  }'
```

---

## 9. Data Conventions & Guardrails

1. **Persistent Source of Truth**: PostgreSQL with PostGIS is the sole store of record for road geometry, incidents, vehicles, and deliveries. Redis stores transient state and events.
2. **Initial Status**: Imported roads default to `UNKNOWN`. Never label roads `OPEN` without operational evidence.
3. **Safety Score**: Bounded between `0` and `100`, where `100` is safer. Disruption probability is a separate `0.0–1.0` value.
4. **Authoritative Blockages**: A confirmed road closure cannot be reopened or overridden by an ML safety score.
5. **Attribution**: Road network data © OpenStreetMap contributors under the Open Database License (ODbL).

---

## 10. Troubleshooting

- **Port Conflict on 55432 or 56379**: Change `POSTGRES_PORT` or `REDIS_PORT` in your `.env` file.
- **Overpass API Rate Limits**: When importing large study corridors, use `--cache-file path/to/file.graphml` to cache the downloaded graph locally.
- **Docker Compose Container Logs**:
  ```bash
  docker compose logs db
  docker compose logs redis
  docker compose logs api
  ```