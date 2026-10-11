# NER-LINK — Master Product Requirements Document

**Project:** NER-LINK — Logistics Accessibility Intelligence Platform for the North Eastern Region  
**Problem statement:** SIH26002  
**Document type:** Product + technical requirements and phased delivery plan  
**Status:** Implementation baseline; decisions marked “provisional” must be confirmed by the team  
**Version:** 1.0

---

## 1. Product vision

NER-LINK helps logistics operators and public authorities understand road accessibility, detect and assess transport disruptions, track essential deliveries, and choose safer routes when conditions change. It combines a road network graph with weather observations, GPS-derived movement, field-officer reports, and potential satellite/remote-sensing detections.

The system must do more than display a map. A meaningful incident should travel through the full workflow:

**Collect evidence → validate and locate it → update incident/road state → calculate road-segment safety → identify affected deliveries → compute an eligible alternate route → update driver and control-room interfaces.**

The initial release targets **one real logistics corridor**, with interfaces and data models designed to expand to additional corridors and districts later. Guwahati–Tawang is a provisional demo corridor only; do not hard-code it into application logic. Keep the study-area boundary configurable.

## 2. Goals

1. Provide a map-based view of roads and current accessibility status for the selected corridor.
2. Allow field officers to submit geo-tagged incident reports with photographs and timestamps.
3. Represent road connectivity as a directed graph whose edges correspond to traversable road segments.
4. Maintain a safety score and current status for each road segment, with source and freshness metadata.
5. Offer two route modes: **Economical / Shortest-distance** for routine logistics and **Fastest-safe** for emergency deliveries.
6. Track vehicles and use available GPS samples to estimate movement/traffic when evidence is sufficient.
7. Propagate relevant changes to the driver and admin dashboards in near real time.
8. Provide a model-integration contract for image detections, evidence parsing/fusion and ML-based safety scoring.
9. Add robust offline field reporting using browser-local storage and idempotent synchronization.
10. Build the platform in tested phases so every phase leaves a working, demonstrable increment.

## 3. Non-goals for the first release

- Claiming live access to government feeds unless an accessible, authorized feed has been verified.
- Claiming satellites can detect every accident or provide continuous live surveillance. Satellite imagery is an asynchronous evidence source for events that are observable at the available resolution and capture time, such as flood extent or some major surface changes.
- Training a trustworthy disruption-prediction model from synthetic data alone.
- Exact monetary route optimization before vehicle, fuel, toll and operating-cost data exists. Until then, “economical” means shortest-distance or a clearly labelled estimated-cost proxy.
- Full production-grade coverage of all eight North Eastern states in Version 1.
- Building a native mobile application; begin with a responsive web app/PWA.
- Microservices, Kafka, Kubernetes or multiple databases unless a measured requirement justifies them.

## 4. Users and roles

### 4.1 Administrator / dispatcher
- View the corridor map, active road incidents, safety levels, vehicle positions and deliveries.
- Review, confirm, reject and resolve field reports.
- Create deliveries and assign vehicles.
- Request route alternatives and compare distance, ETA, risk and route mode.
- Receive alerts when trips or critical deliveries are affected.

### 4.2 Field officer
- Create an incident report with type, severity, description, GPS/map location, observed time and photographs.
- Save a report while offline and synchronize it later.
- View synchronization state and report status.
- See permitted alerts and update assigned reports if authorized.

### 4.3 Driver / transport operator
- View assigned trip, route, destination, cargo priority and latest ETA.
- Share location with explicit browser/device permission while a trip is active.
- Receive route-change and disruption alerts.
- Acknowledge critical route updates.

### 4.4 Intelligence services
- Ingest and normalize external observations.
- Return image-detection candidates with confidence and provenance.
- Return a per-segment disruption probability/safety score with model version and validity horizon.
- Never silently override a confirmed safety restriction.

## 5. Architecture principles and technology baseline

### 5.1 Initial architecture

Use a modular monolith for the application backend plus a separate worker process when asynchronous jobs are needed.

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS.
- **Map:** MapLibre GL JS. Render server-provided road and incident geometries; the frontend does not own route algorithms.
- **Backend:** Python + FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Persistent store:** PostgreSQL + PostGIS; source of truth for roads, incidents, trips, route recommendations, scores and audit history.
- **Real-time / transient state:** Redis for latest vehicle state, caching and event distribution. Redis is server-side; it is not offline device storage.
- **Client offline storage:** IndexedDB + Service Worker/PWA. Dexie.js may be used as an IndexedDB wrapper.
- **Road source:** OpenStreetMap with attribution and licence compliance.
- **Initial graph/routing implementation:** Build a routable directed graph for the chosen study area, using OSMnx/NetworkX or another documented topology-preserving importer. Start with Dijkstra; A* is optional after correctness is established. Persist canonical node/edge IDs and geometry in PostGIS. Do not use disconnected line strings as if they automatically form a routable graph.
- **Weather:** Start with an accessible provider such as Open-Meteo. Treat IMD/government feeds as optional integrations until access, terms and coverage are confirmed.
- **ML:** Python, scikit-learn and XGBoost for tabular risk prediction when suitable labelled data exists; PyTorch only for an appropriate image/remote-sensing model.
- **Image/object storage:** Local development storage initially; object storage in deployment. Store file metadata/URL in PostgreSQL, not the binary image itself.
- **Deployment:** Docker Compose locally; automated checks through GitHub Actions.

### 5.2 Architecture guardrails

1. PostgreSQL/PostGIS is the source of truth; Redis is not the only store for any critical business record.
2. The frontend renders road geometry and sends origin/destination coordinates. The backend snaps coordinates to graph nodes and calculates paths. Do not build a second, inconsistent routing graph in the frontend.
3. The backend owns stable road-segment IDs and exposes them to frontend and ML services.
4. ML services return predictions; they do not write directly into arbitrary database tables. The backend validates and persists their outputs.
5. Field reports, satellite candidates, weather observations and GPS samples retain provenance and timestamps.
6. Unknown/stale data must be shown as unknown/stale, not silently treated as safe or current.
7. A model prediction cannot reopen a road marked blocked by an authoritative/confirmed closure.
8. External-service failure must degrade gracefully; do not fabricate routes, data or model outputs.

## 6. Four major product areas

### Area A — Information collection centre

Inputs:
- Static road network and geographic boundaries.
- Weather observations and forecasts.
- Driver/vehicle GPS points.
- Field reports and photographs.
- Satellite/remote-sensing scenes and derived candidate detections.

Requirements:
- Normalize timestamps to UTC in storage and preserve source-local time when useful.
- Store source/provider, capture/observation time, ingestion time and relevant coordinates/geometry.
- Validate units, coordinate bounds, payload size and file type.
- Reject malformed data and report useful errors.
- Mark observations stale after source-specific freshness limits.
- Spatially associate each observation with relevant road segment(s), preserving the original observation.
- Avoid treating a single noisy signal as confirmed truth.

### Area B — Image processing and evidence fusion

Two distinct outputs must not be conflated:

**Image-detection confidence:** confidence that the image model recognized an image class (for example, possible flood/water extent or visible road obstruction).

**Incident confidence:** confidence that a real road-disrupting event exists at a specific location, based on image evidence plus provenance, location/time matching, other sources and human review.

Workflow:
1. Field images and satellite scenes enter a processing queue.
2. Validate image type, size, metadata, acquisition time and georeferencing.
3. Run the selected detector/change-analysis model asynchronously.
4. Return class, confidence, affected polygon/point, source image ID, model version and processing time.
5. Match candidate geometry to road segments.
6. Correlate the candidate with rainfall/weather, GPS slowdowns, other reports and existing events.
7. Create a candidate incident, not a confirmed blockage, unless policy and corroborating evidence permit an automatic state transition.
8. Expose the candidate to a human reviewer where required.

Satellite scope must be selected by evidence and data availability. Flood extent and some large, visible terrain/surface changes are better initial targets than small vehicle accidents. Do not promise satellite detection of every accident or real-time detection where imagery cadence cannot support it.

### Area C — Road graph and safety intelligence

The map's routeable network is a **directed graph**:
- **Node:** a road intersection or routable endpoint.
- **Edge:** a traversable directed road segment connecting two nodes.
- **Geometry:** line shown on the map.
- **Static attributes:** OSM way ID, road class, one-way/access restrictions, length, geometry and base speed/estimated travel time.
- **Dynamic attributes:** status, safety score, risk/probability, estimated speed/traffic, data freshness, reasons and latest update.

Minimum edge fields:
- `id` — canonical internal ID.
- `osm_way_id` and graph identity (`u`, `v`, and key where parallel edges exist).
- `source_node_id`, `target_node_id`.
- `geometry` (PostGIS line geometry).
- `length_m`.
- `base_travel_time_s` or fields needed to derive it.
- `oneway`, `access_allowed`, `road_class`.
- Current `status`: `UNKNOWN`, `OPEN`, `AT_RISK`, `RESTRICTED`, `BLOCKED`.
- `safety_score` from 0 to 100, where 100 means safer and 0 means least safe.
- `disruption_probability` from 0 to 1 where available.
- `score_confidence` from 0 to 1 where available.
- `score_valid_until`, `score_updated_at`, `score_model_version`.
- `status_reason_codes` and data provenance references.

The ML team's intended safety score can be derived from predicted disruption probability: `safety_score = 100 * (1 - disruption_probability)`. This conversion is only valid when the model probability is calibrated/meaningful; otherwise label the value as a baseline heuristic score, not a probability. Confirmed hard closures are enforced independently from the safety score.

The system should use a rule-based baseline before introducing trained ML. ML input/output formats must be stable so the backend can run with a mock provider while the model is being built.

### Area D — Routing, tracking and response

Two modes:

**Mode 1 — Economical / shortest-distance (routine logistics):**
- Primary objective at MVP: minimize total distance among admissible routes. This is a transparent distance proxy, not a claim of exact rupee cost.
- Later, add estimated operating cost only when distance, vehicle/fuel parameters and toll data are available.
- Exclude confirmed blocked edges; apply a configurable risk penalty or safety eligibility threshold to avoid unacceptable risk.

**Mode 2 — Fastest-safe (emergency logistics):**
- Minimize predicted travel time subject to hard exclusions for confirmed blocked roads and configured safety constraints.
- A shorter ETA must never override a confirmed closure.
- Return “no safe route found” and alert the dispatcher if no admissible route exists.

For each recommendation return route geometry, ordered edge IDs, distance, ETA, mode, score/risk summary, avoided hazards, computation time and timestamp. Recalculate only when a meaningful event occurs (confirmed closure, significant risk change, major GPS deviation or updated route constraint), not for every insignificant GPS ping.

Vehicle/traffic requirements:
- Driver location updates are accepted only from authorized active trips.
- Reject impossible coordinates and stale/out-of-order pings.
- Snap GPS points to the road graph where feasible; record map-matching confidence.
- Aggregate segment speeds only when enough sufficiently recent samples exist. Show traffic as `UNKNOWN` when sample volume is inadequate.
- Maintain latest location in Redis and persist trip history at a configurable rate/retention policy.

## 7. Safety and decision rules

1. `BLOCKED` is a hard routing exclusion.
2. `RESTRICTED` and low-safety edges are excluded or penalized according to explicit mode policy.
3. `UNKNOWN` does not mean safe. The route policy must state how unknown edges are treated; critical/emergency mode should be conservative.
4. A single low-confidence image candidate must not automatically become an authoritative closure.
5. A driver must see a clear route update and its reason. Where policy calls for dispatcher approval, the route is a recommendation until approved.
6. When no admissible route exists, stop route recommendation and escalate instead of inventing a path.
7. All score, incident and route changes must retain timestamps and source/model versions for auditability.

## 8. Core data model

Implement migrations for these entities as needed by the current phase; do not create fake functionality solely to populate every table on day one.

- `users`: identity, role, preferred language, active state.
- `districts`: name, state, boundary geometry.
- `road_nodes`: canonical node ID and point geometry.
- `road_segments`: topology, stable ID, OSM identifiers, edge geometry, length, access/direction attributes and base route attributes.
- `road_segment_state`: current status/safety score, reasons, freshness and source references.
- `incidents`: type, severity, description, location, status, reporter, timestamps and verification audit fields.
- `incident_evidence`: image reference, source type, capture time, model class/confidence if available.
- `weather_observations`: provider, location/coverage, values/units, observation time and ingestion time.
- `satellite_events`: acquisition details, candidate geometry/class/confidence/model version/review state.
- `vehicles`: identifier, type, capacity if known, active state.
- `vehicle_locations`: time-stamped positions, speed/heading if available, source and map-match fields.
- `deliveries`: cargo class, priority, origin/destination, deadline and status.
- `trips`: vehicle/delivery assignment, active state, route reference and lifecycle timestamps.
- `route_recommendations`: mode, ordered edge IDs/route geometry, distance, ETA, score/risk summary, reason, status and timestamp.
- `risk_predictions`: target edge, horizon, probability/score/confidence, features/provenance reference, model version and timestamps.
- `alerts`: recipient/role, event, severity, channel, acknowledgement and delivery status.
- `audit_logs`: actor, action, entity, before/after reference, timestamp.

Use foreign keys, constraints, appropriate geometry types and spatial indexes. Preserve incident history; resolving an incident must not erase it.

## 9. API and event contracts

Use a versioned API prefix `/api/v1`. Initial route groups:
- `/roads` — road geometry, details and status.
- `/incidents` — create/list/detail/confirm/reject/resolve.
- `/vehicles` — vehicle list and location ingestion.
- `/deliveries` and `/trips` — create and track logistics work.
- `/routes/plan` — calculate a route using origin, destination, mode and constraints.
- `/risk` — road score, risk map and summary.
- `/weather` — latest stored observations and freshness.
- `/satellite-events` — list/review candidate detections.
- `/alerts` — list/acknowledge alerts.
- `/dashboard` — aggregated counts and map layers.

Use OpenAPI generated by FastAPI as the source for API documentation. Request/response schemas are explicit and validated.

Minimum event names:
- `incident.created`
- `incident.confirmed`
- `incident.resolved`
- `road.status_changed`
- `road.risk_changed`
- `weather.updated`
- `vehicle.location_updated`
- `route.recalculated`
- `delivery.at_risk`
- `alert.created`

Event envelope must include `event_id`, `event_type`, `occurred_at`, `entity_id`, `schema_version`, `source` and a small payload. Consumers must be idempotent. Use Redis Pub/Sub for live UI fan-out; use Redis Streams or a durable database-backed job/outbox mechanism for work that must survive consumer disconnection. Do not rely on Pub/Sub alone for critical workflows.

### Model-service output contract

Image detection candidate:
```json
{
  "candidate_id": "string",
  "source_image_id": "string",
  "event_class": "possible_flood",
  "detection_confidence": 0.0,
  "geometry": "GeoJSON geometry",
  "acquired_at": "ISO-8601 timestamp or null",
  "model_name": "string",
  "model_version": "string"
}
```

Road-segment score:
```json
{
  "road_segment_id": "canonical ID",
  "disruption_probability": 0.0,
  "safety_score": 100,
  "score_confidence": 0.0,
  "prediction_horizon_minutes": 360,
  "reason_codes": ["heavy_rainfall", "nearby_incident"],
  "input_observed_at": "ISO-8601 timestamp",
  "model_name": "string",
  "model_version": "string"
}
```

Values above are schema examples, not claimed model outputs. Reject invalid ranges and mismatched road IDs. Record model and input freshness.

## 10. Offline field reporting

- The field PWA stores pending forms and photograph references/blobs in IndexedDB.
- The client creates a UUID for each report before attempting upload.
- The backend enforces uniqueness/idempotency for that client-generated ID.
- Synchronization states: `PENDING`, `SYNCING`, `SYNCED`, `FAILED`.
- Retry with bounded backoff; do not delete pending data until acknowledgement is received.
- Show last sync time and visible error state.
- Preserve observation time separately from server receipt time.
- Redis is not the client’s offline database. Redis is server-side and cannot make a disconnected browser submit data.
- Push notifications are not guaranteed while a device is fully offline; queue/refresh state after reconnection.

## 11. Security, observability and reliability

- Role-based permissions enforced by the API, not just UI controls.
- Password hashing via a standard password-hashing library; secrets only in environment/secret manager.
- Validate coordinate ranges, image MIME/type/size and request payload limits.
- Avoid exposing private driver locations to users without permission.
- Log meaningful actions and failures; never log passwords/tokens.
- Add `/health/live` and `/health/ready` endpoints.
- Distinguish unavailable/stale external data from current data.
- Use database backups and document restore steps for deployed instances.
- Keep user uploads outside the web root and restrict retrieval based on authorization.
- Use transactions for status changes and route/alert creation where consistency matters.

## 12. Test strategy and definition of done

Every phase must include tests for the feature it introduces. A phase is not complete solely because code compiles.

### Automated layers
- Unit tests for status transitions, route weights, constraints, validation and idempotency.
- Integration tests against PostGIS and Redis.
- API tests for authentication, authorization, valid/invalid requests and error paths.
- Frontend tests for incident, route and status interactions.
- Playwright end-to-end tests for the complete disruption-to-reroute flow.
- Load tests after correctness is established, using stated and repeatable test parameters.

### Required end-to-end scenario
1. Create an authorized user, vehicle and medicine delivery.
2. Calculate and display an initial admissible route.
3. Submit a geo-tagged blockage report near one of the route’s edges.
4. Review/confirm the incident.
5. Verify the affected edge changes status and affected trip is discovered.
6. Verify a blocked edge is never included in the new route.
7. Verify alternatives are ranked according to selected route mode.
8. Verify ETA and route update are persisted and broadcast to authorized clients.
9. Verify duplicate event/report retries do not duplicate incidents or route-change actions.
10. Verify a no-safe-route case returns a clear failure and dispatcher alert.
11. Verify offline field report sync and idempotency after reconnecting.

### General definition of done
- Acceptance criteria pass.
- Migrations are included and reviewed.
- No secrets committed.
- Tests added and passing for changed behaviour.
- API docs updated.
- User-visible data has clear freshness/status labels.
- Known limitations are documented.
- No unsupported claims about model accuracy or live feeds.

## 13. Phased roadmap and acceptance criteria

### Phase 0 — Repository and local infrastructure
Build repository structure, FastAPI and frontend skeletons, Docker Compose, PostGIS/Redis, config validation, health checks, CI and setup docs.

**Acceptance:** clean setup documented; services start; health endpoints report dependencies correctly; secrets remain out of Git.

### Phase 1 — Real road network and database
Implement migrations, road nodes/edges and spatial tables. Import the selected corridor's routable OpenStreetMap graph, preserving topology, one-way/access rules, stable edge IDs and geometries. Expose read-only road/GeoJSON APIs.

**Acceptance:** graph has connected routeable nodes/edges; valid paths can be calculated between known points; road geometry appears on the map; import is reproducible; attribution is shown.

### Phase 2 — Field incidents
Build incident API, evidence upload/storage, review lifecycle, map display, role checks and audit history.

**Acceptance:** field report persists with coordinates/time/source; authorized official can review it; state change has an audit trail.

### Phase 3 — Delivery and dual-mode routing
Build vehicles, deliveries, trips, coordinate snapping, shortest-distance/economical mode, fastest-safe mode, blocked-edge filtering and route persistence.

**Acceptance:** both modes produce distinguishable routes where alternatives exist; blocked segments are excluded; no-safe-path is handled correctly; route result has distance/ETA/reason.

### Phase 4 — GPS and real-time propagation
Build authorized trip location ingestion, latest state in Redis, location history policy, WebSockets and event-triggered rerouting/alerts.

**Acceptance:** vehicle movement is reflected live; stale pings do not overwrite newer state; incident changes update affected trips without manual refresh.

### Phase 5 — Weather and baseline safety score
Integrate one weather provider, store provenance/freshness, implement an explainable baseline score, overlay score/status on graph and apply constraints/penalties to routing.

**Acceptance:** test inputs change relevant scores/ranking; stale/missing weather is visible; hard closure overrides score.

### Phase 6 — ML scoring and evidence parser
Integrate the ML team's stable contracts, preprocessing and validated model artifact. Keep a rule-based fallback. Evaluate predictions using held-out relevant data.

**Acceptance:** inference output passes range/freshness/schema checks; model version is recorded; evaluation results are documented; absence of a model never breaks core routing.

### Phase 7 — Image/satellite candidate pipeline
Build async image processing, candidate detections, geometry-to-road matching, evidence fusion and review workflow for one defensible event category.

**Acceptance:** a test image/scene yields a candidate with source, geometry, class and confidence; it does not silently create a confirmed closure; confirmed candidate uses the normal rerouting workflow.

### Phase 8 — Offline PWA and multilingual interface
Build IndexedDB sync queue, Service Worker caching, photo retry, translated interface and notification state handling.

**Acceptance:** offline form survives restart, syncs once on reconnection and shows failures; translation changes visible UI strings.

### Phase 9 — Stabilization and deployment
Add monitoring, load tests, backups, access-control review, UI polish, demo scenarios and deployment documentation.

**Acceptance:** repeatable end-to-end demo and documented deployment; no hidden manual database edits are required.

## 14. Team ownership and integration

### Backend team
Owns:
- Data source adapters and ingestion APIs.
- Road graph construction/storage and stable edge identifiers.
- PostgreSQL/PostGIS schema and migrations.
- Path computation and route-mode semantics.
- GPS ingestion, map-matching interface and traffic sample aggregation.
- Redis state/event transport, WebSocket backend and real-time orchestration.
- Incident, trip, delivery and alert business workflows.
- API contracts, integration tests and backend deployment.

### AI/ML team
Owns:
- Data parser/normalizer used for model inputs.
- Image-processing pipeline for field photos and selected satellite scenes.
- Detection candidates, image confidence and geospatial output.
- Road-segment risk/disruption prediction model.
- Training/evaluation pipeline, model versioning, inference interface and model limitations.
- Documented feature definitions and model-service contract.

### Frontend team
Owns:
- Admin/control-room map and dashboards.
- Driver dashboard and live status/route updates.
- Field-officer reporting UI and PWA experience.
- Map layers, map selection and displaying GeoJSON/route geometry from the backend.
- Offline IndexedDB queue and visible synchronization status.
- API integration, frontend tests and usability.

### Important responsibility boundary
The frontend **renders** the graph/map and sends origin/destination coordinates. The backend owns graph topology, canonical edge IDs, snapping and shortest-path calculation. Do not create an independent frontend routing graph. The ML team provides predictions using canonical road-segment IDs; it does not silently modify the database. The backend validates model output and applies it according to the safety policy.

### Integration protocol
- Keep OpenAPI documentation current.
- Store shared JSON examples/contracts in `docs/contracts/`.
- Use stable IDs and UTC timestamps.
- Require `schema_version` for asynchronous event payloads.
- Provide mock responses/fixtures so each team can work before live integration.
- Integrate after each phase, not only near the deadline.
- Each PR must state tests run and known limitations.

## 15. Risk register

| Risk | Mitigation |
|---|---|
| Poor/incomplete road topology | Validate connectivity, one-way rules and route examples before adding ML. |
| Weak historical labels | Use an explicit rule baseline; don't claim ML performance without holdout evaluation. |
| False image detection | Keep candidate confidence separate from incident confidence; human review and evidence fusion. |
| Delayed/unavailable satellite scenes | Treat imagery as asynchronous evidence; keep field/GPS/weather workflows operational. |
| GPS noise or insufficient samples | Reject stale/impossible points; display traffic as unknown when evidence is insufficient. |
| Duplicate/offline uploads | Client-generated idempotency key and server-side unique constraint. |
| Redis event loss | Use durable jobs/Streams or an outbox for critical work; Pub/Sub only for appropriate fan-out. |
| Route service failure | Show failure/stale route explicitly; never invent a route. |
| Scope creep | Complete the end-to-end MVP before multi-region scale or advanced CV. |
| Unclear “cost” metric | Start with shortest distance; add monetary cost only after defining inputs and units. |

## 16. Build order for the first implementation cycle

1. Repository structure, environment config and Docker Compose.
2. FastAPI live/ready health endpoints.
3. PostgreSQL/PostGIS connection and first reviewed Alembic migration.
4. Road node/edge schema and repeatable OSM import for the configured study area.
5. Tests for graph connectivity, direction restrictions and coordinate snapping.
6. Read-only road GeoJSON API and basic map view.
7. Only after this foundation is verified: incident reporting, routing modes, GPS, ML and satellite work.

## 17. Agentic coding instructions (Antigravity / AG)

This document is the **master PRD**, not a request to implement the entire product in one pass.

For each agent session:
1. Read this PRD and the current repository state.
2. Implement only the specifically named phase and its acceptance criteria.
3. First inspect existing files and report what already exists; do not overwrite working code blindly.
4. Propose a brief file-level plan before editing.
5. Implement a coherent vertical slice with tests.
6. Run the available tests, formatters, migrations and service checks; report exact commands and outcomes.
7. If a dependency/service is unavailable, report the blocker and provide a deterministic test/mocked fallback rather than claiming success.
8. Do not implement future phases prematurely.
9. Do not change shared API/database contracts without updating this PRD/contracts and explaining the impact on all three teams.
10. Do not fabricate API keys, live government feeds, model accuracy, satellite detections or test results.
11. Preserve existing user changes and inspect `git status` before making destructive changes.
12. End with: changed files, design decisions, tests run/results, manual verification steps, known limitations and the next smallest task.

**Immediate implementation scope:** Phase 0 plus the initial portion of Phase 1 only. Start with repository setup, Docker Compose, PostGIS/Redis health, database models/migrations, and a topology-preserving OSM graph import for a configurable study area. Do not implement ML, satellite AI, offline sync or the full dashboard in this first coding session.
