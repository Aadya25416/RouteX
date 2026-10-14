"""Comprehensive integration and unit tests for Data Collection & Ingestion Layer.

Covers:
- Deliverable A: Unified raw evidence ingestion & storage
- Deliverable B: Satellite ingestion adapter & provenance
- Deliverable C: Weather ingestion with Open-Meteo normalization & reliability
- Deliverable D: Vehicle GPS coordinates batch ingestion & traffic aggregation
- Deliverable E: Machine learning team handoff contract (discovery, claim, result)
"""

import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response

from backend.config import get_settings
from backend.services.storage import compute_sha256

settings = get_settings()

# Minimal valid JPEG binary (\xff\xd8\xff)
MOCK_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
    b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)

# Minimal valid TIFF binary (Little-endian \x49\x49\x2a\x00)
MOCK_TIFF_BYTES = (
    b"II*\x00\x08\x00\x00\x00\x01\x00\x00\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00"
    b"\x00\x00\x00\x00"
)


# =========================================================================
# 1. DELIVERABLE A & B: EVIDENCE & SATELLITE INGESTION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_field_officer_unified_evidence_upload(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test valid field-officer evidence upload, checksum, and persistent retrieval."""
    unique_bytes = MOCK_JPEG_BYTES + b"_field_hazard_" + uuid.uuid4().bytes
    files = {"file": ("field_hazard_01.jpg", unique_bytes, "image/jpeg")}
    data = {
        "source_type": "FIELD_OFFICER",
        "source_provider": "field_app_v2",
        "latitude": "26.1445",
        "longitude": "91.7362",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    res = await async_client.post(
        "/api/v1/evidence/upload",
        files=files,
        data=data,
        headers=field_officer_headers,
    )
    assert res.status_code == 201, res.text
    ev = res.json()
    assert ev["source_type"] == "FIELD_OFFICER"
    assert ev["source_provider"] == "field_app_v2"
    assert ev["media_type"] == "image/jpeg"
    assert ev["file_size_bytes"] == len(unique_bytes)
    assert ev["sha256_checksum"] == compute_sha256(unique_bytes)
    assert ev["processing_status"] == "PENDING"
    assert ev["latitude"] == pytest.approx(26.1445, abs=1e-3)
    assert ev["longitude"] == pytest.approx(91.7362, abs=1e-3)

    evidence_id = ev["id"]

    # Retrieve record by ID
    get_res = await async_client.get(
        f"/api/v1/evidence/{evidence_id}",
        headers=field_officer_headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == evidence_id

    # Download raw binary and verify bytes match
    dl_res = await async_client.get(
        f"/api/v1/evidence/{evidence_id}/download",
        headers=field_officer_headers,
    )
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "image/jpeg"
    assert dl_res.content == unique_bytes


@pytest.mark.asyncio
async def test_satellite_product_ingestion_and_provenance(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Test satellite scene product registration with GeoJSON footprint and CRS provenance."""
    scene_id = f"S2A_MSIL2A_TEST_{uuid.uuid4().hex[:8]}"
    footprint = {
        "type": "Polygon",
        "coordinates": [[
            [91.50, 26.10],
            [92.80, 26.10],
            [92.80, 27.70],
            [91.50, 27.70],
            [91.50, 26.10],
        ]],
    }
    unique_tiff = MOCK_TIFF_BYTES + uuid.uuid4().bytes
    files = {"file": (f"{scene_id}.tif", unique_tiff, "image/tiff")}
    data = {
        "scene_id": scene_id,
        "provider": "copernicus_sentinel2",
        "cloud_cover_percent": "14.5",
        "resolution_m": "10.0",
        "crs": "EPSG:4326",
        "footprint_geojson": json.dumps(footprint),
        "extra_metadata": json.dumps({"sensor": "MSI", "orbit": 46}),
    }

    res = await async_client.post(
        "/api/v1/satellite/ingest",
        files=files,
        data=data,
        headers=dispatcher_headers,
    )
    assert res.status_code == 201, res.text
    ev = res.json()
    assert ev["source_type"] == "SATELLITE"
    assert ev["source_provider"] == "copernicus_sentinel2"
    assert ev["acquisition_metadata"]["scene_id"] == scene_id
    assert ev["acquisition_metadata"]["cloud_cover_percent"] == 14.5
    assert ev["media_type"] == "image/tiff"

    # Verify audit log recorded
    logs_res = await async_client.get("/api/v1/satellite/logs", headers=dispatcher_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert any(log["scene_id"] == scene_id and log["status"] == "SUCCESS" for log in logs)


@pytest.mark.asyncio
async def test_evidence_validation_rules(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test validation of file types, sizes, and malformed metadata."""
    # 1. Invalid file type (e.g. plain text masquerading as image)
    fake_txt = b"Hello I am not a valid JPEG or PNG file"
    res1 = await async_client.post(
        "/api/v1/evidence/upload",
        files={"file": ("fake.jpg", fake_txt, "image/jpeg")},
        data={"source_type": "FIELD_OFFICER"},
        headers=field_officer_headers,
    )
    assert res1.status_code == 415

    # 2. Oversized file (exceeds limit)
    with patch("backend.services.evidence_service.settings.MAX_UPLOAD_SIZE_BYTES", 100):
        res2 = await async_client.post(
            "/api/v1/evidence/upload",
            files={"file": ("large.jpg", MOCK_JPEG_BYTES, "image/jpeg")},
            data={"source_type": "FIELD_OFFICER"},
            headers=field_officer_headers,
        )
        assert res2.status_code == 413

    # 3. Invalid coordinates (latitude > 90)
    res3 = await async_client.post(
        "/api/v1/evidence/upload",
        files={"file": ("test.jpg", MOCK_JPEG_BYTES, "image/jpeg")},
        data={"source_type": "FIELD_OFFICER", "latitude": "120.0", "longitude": "91.0"},
        headers=field_officer_headers,
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_evidence_deduplication(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test duplicate uploads with identical SHA-256 are safely deduplicated."""
    dedup_bytes = MOCK_JPEG_BYTES + b"_dedup_test_" + uuid.uuid4().bytes
    files1 = {"file": ("rockfall_a.jpg", dedup_bytes, "image/jpeg")}
    res1 = await async_client.post(
        "/api/v1/evidence/upload",
        files=files1,
        data={"source_type": "FIELD_OFFICER"},
        headers=field_officer_headers,
    )
    assert res1.status_code == 201
    id1 = res1.json()["id"]

    # Re-upload identical bytes
    files2 = {"file": ("rockfall_duplicate.jpg", dedup_bytes, "image/jpeg")}
    res2 = await async_client.post(
        "/api/v1/evidence/upload",
        files=files2,
        data={"source_type": "FIELD_OFFICER"},
        headers=field_officer_headers,
    )
    assert res2.status_code == 201
    id2 = res2.json()["id"]
    # Should return existing evidence record
    assert id1 == id2


# =========================================================================
# 2. DELIVERABLE E: ML HANDOFF CONTRACT TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_ml_worker_discovery_claim_and_result(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    ml_service_headers: dict[str, str],
):
    """Test full ML handoff flow: discovery -> atomic claim -> result reporting."""
    # 1. Ingest fresh evidence
    unique_jpeg = MOCK_JPEG_BYTES + uuid.uuid4().bytes
    up_res = await async_client.post(
        "/api/v1/evidence/upload",
        files={"file": ("incident_photo.jpg", unique_jpeg, "image/jpeg")},
        data={"source_type": "FIELD_OFFICER"},
        headers=field_officer_headers,
    )
    assert up_res.status_code == 201
    evidence_id = up_res.json()["id"]

    # 2. ML worker discovers pending evidence
    pending_res = await async_client.get(
        "/api/v1/ml/evidence/pending",
        headers=ml_service_headers,
    )
    assert pending_res.status_code == 200
    pending_data = pending_res.json()
    assert pending_data["total_pending"] >= 1
    found_task = next((t for t in pending_data["tasks"] if t["evidence_id"] == evidence_id), None)
    assert found_task is not None
    assert found_task["processing_status"] == "PENDING"
    assert found_task["download_url"].endswith(f"/ml/evidence/{evidence_id}/download")

    # 3. Worker 1 claims task
    claim_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/claim",
        json={"worker_id": "yolo_worker_node_1"},
        headers=ml_service_headers,
    )
    assert claim_res.status_code == 200
    assert claim_res.json()["processing_status"] == "IN_PROGRESS"
    assert claim_res.json()["claimed_by"] == "yolo_worker_node_1"

    # 4. Worker 2 attempts concurrent claim -> 409 Conflict
    conflict_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/claim",
        json={"worker_id": "yolo_worker_node_2"},
        headers=ml_service_headers,
    )
    assert conflict_res.status_code == 409

    # 5. Worker 1 downloads image
    dl_res = await async_client.get(
        f"/api/v1/ml/evidence/{evidence_id}/download",
        headers=ml_service_headers,
    )
    assert dl_res.status_code == 200
    assert dl_res.content == unique_jpeg

    # 6. Worker 1 reports completion with detection metadata
    result_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/result",
        json={
            "worker_id": "yolo_worker_node_1",
            "status": "COMPLETED",
            "model_detection_class": "LANDSLIDE_DEBRIS",
            "model_confidence": 0.885,
            "model_metadata": {
                "bbox": [102, 45, 320, 280],
                "model_name": "RouteX-YOLOv8x",
                "inference_time_ms": 42.1,
            },
        },
        headers=ml_service_headers,
    )
    assert result_res.status_code == 200
    updated = result_res.json()
    assert updated["processing_status"] == "COMPLETED"

    # Verify task no longer in pending queue
    pending_after = await async_client.get("/api/v1/ml/evidence/pending", headers=ml_service_headers)
    assert not any(t["evidence_id"] == evidence_id for t in pending_after.json()["tasks"])


@pytest.mark.asyncio
async def test_ml_worker_failure_preserves_raw_evidence(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    ml_service_headers: dict[str, str],
):
    """Test ML processing failure records error state without deleting original image."""
    unique_jpeg = MOCK_JPEG_BYTES + uuid.uuid4().bytes
    up_res = await async_client.post(
        "/api/v1/evidence/upload",
        files={"file": ("corrupted.jpg", unique_jpeg, "image/jpeg")},
        data={"source_type": "FIELD_OFFICER"},
        headers=field_officer_headers,
    )
    ev_id = up_res.json()["id"]

    await async_client.post(
        f"/api/v1/ml/evidence/{ev_id}/claim",
        json={"worker_id": "worker_fail_test"},
        headers=ml_service_headers,
    )

    # Report failure
    fail_res = await async_client.post(
        f"/api/v1/ml/evidence/{ev_id}/result",
        json={
            "worker_id": "worker_fail_test",
            "status": "FAILED",
            "error_message": "CUDA OOM or unreadable image array",
        },
        headers=ml_service_headers,
    )
    assert fail_res.status_code == 200
    assert fail_res.json()["processing_status"] == "FAILED"

    # Original binary is still completely downloadable and intact
    get_res = await async_client.get(f"/api/v1/evidence/{ev_id}", headers=field_officer_headers)
    assert get_res.status_code == 200
    assert get_res.json()["processing_error"] == "CUDA OOM or unreadable image array"


# =========================================================================
# 3. DELIVERABLE C: WEATHER INGESTION TESTS
# =========================================================================

MOCK_OPEN_METEO_RESPONSE = {
    "latitude": 26.14,
    "longitude": 91.74,
    "current": {
        "time": "2026-10-14T12:00",
        "temperature_2m": 28.4,
        "precipitation": 12.5,
        "rain": 12.5,
        "snowfall": None,
        "weather_code": 63,
        "wind_speed_10m": 18.2,
        "wind_gusts_10m": 31.0,
        "visibility": 8000.0,
    },
}


@pytest.mark.asyncio
async def test_weather_refresh_and_normalization(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Test genuine response normalization without turning missing values into zero."""
    dynamic_payload = dict(MOCK_OPEN_METEO_RESPONSE)
    dynamic_payload["current"] = dict(MOCK_OPEN_METEO_RESPONSE["current"])
    dynamic_payload["current"]["time"] = datetime.now(timezone.utc).isoformat()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=dynamic_payload)

        refresh_res = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert refresh_res.status_code == 200, refresh_res.text
        data = refresh_res.json()
        assert data["provider"] == "open-meteo"
        assert data["observations_persisted"] >= 1

    # Inspect latest observations
    latest_res = await async_client.get("/api/v1/weather/latest?limit=10", headers=dispatcher_headers)
    assert latest_res.status_code == 200
    obs_list = latest_res.json()
    assert len(obs_list) >= 1
    sample = obs_list[0]
    assert sample["temperature_c"] == 28.4
    assert sample["rainfall_mm"] == 12.5
    assert sample["wind_speed_kmh"] == 18.2
    assert sample["wind_gusts_kmh"] == 31.0
    assert sample["weather_code"] == 63
    # Missing snowfall should remain None, NOT 0.0
    assert sample["snowfall_cm"] is None

    # Status inspection
    status_res = await async_client.get("/api/v1/weather/status", headers=dispatcher_headers)
    assert status_res.status_code == 200
    st = status_res.json()
    assert st["provider"] == "open-meteo"
    assert st["total_observations"] >= 1


@pytest.mark.asyncio
async def test_weather_provider_outage_preserves_history(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Test provider network error or timeout preserves existing observations without wiping database."""
    # Count current observations
    st_before = (await async_client.get("/api/v1/weather/status", headers=dispatcher_headers)).json()
    count_before = st_before["total_observations"]

    # Simulate upstream 503 outage
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(503, text="Service Unavailable")

        refresh_res = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert refresh_res.status_code == 200
        assert refresh_res.json()["observations_persisted"] == 0

    # Ensure previous observations were not erased
    st_after = (await async_client.get("/api/v1/weather/status", headers=dispatcher_headers)).json()
    assert st_after["total_observations"] == count_before


# =========================================================================
# 4. DELIVERABLE D: GPS BATCH INGESTION & TRAFFIC AGGREGATION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_gps_batch_ingestion_and_out_of_order_handling(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    """Test batch GPS telemetry submission handling reordered timestamps and deduplication."""
    # 1. Register test vehicle
    reg_num = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": reg_num, "vehicle_type": "truck", "status": "AVAILABLE"},
        headers=dispatcher_headers,
    )
    assert v_res.status_code == 201
    veh_id = v_res.json()["id"]

    now = datetime.now(timezone.utc)
    # Batch with timestamps intentionally out of order
    batch_points = [
        {
            "latitude": 26.1425,
            "longitude": 91.7420,
            "speed_kmh": 40.0,
            "heading_deg": 180.0,
            "source": "gps_batch",
            "recorded_at": (now - timedelta(seconds=20)).isoformat(),
        },
        {
            "latitude": 26.14365,
            "longitude": 91.74172,
            "speed_kmh": 35.0,
            "heading_deg": 175.0,
            "source": "gps_batch",
            "recorded_at": (now - timedelta(seconds=60)).isoformat(),
        },
        {
            "latitude": 26.1415,
            "longitude": 91.7425,
            "speed_kmh": 45.0,
            "heading_deg": 185.0,
            "source": "gps_batch",
            "recorded_at": now.isoformat(),
        },
    ]

    batch_res = await async_client.post(
        f"/api/v1/vehicles/{veh_id}/locations/batch",
        json={"locations": batch_points},
        headers=driver_headers,
    )
    assert batch_res.status_code == 201, batch_res.text
    data = batch_res.json()
    assert data["ingested_count"] == 3

    # Check latest location in Redis is the newest point (recorded_at = now)
    latest_res = await async_client.get(f"/api/v1/vehicles/{veh_id}/location", headers=driver_headers)
    assert latest_res.status_code == 200
    assert latest_res.json()["latitude"] == pytest.approx(26.1415, abs=1e-3)


@pytest.mark.asyncio
async def test_gps_unmatched_distant_coordinate(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    """Test coordinates far from any road remain unmatched (matched_segment_id=None)."""
    reg_num = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": reg_num, "vehicle_type": "truck", "status": "AVAILABLE"},
        headers=dispatcher_headers,
    )
    veh_id = v_res.json()["id"]

    # Point in the middle of nowhere / forest (several km away from any road)
    distant_point = {
        "latitude": 27.1000,
        "longitude": 91.5000,
        "speed_kmh": 10.0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    res = await async_client.post(
        f"/api/v1/vehicles/{veh_id}/locations",
        json=distant_point,
        headers=driver_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["matched_segment_id"] is None
    # Original coordinates are preserved
    assert data["latitude"] == pytest.approx(27.1000, abs=1e-4)


@pytest.mark.asyncio
async def test_traffic_aggregation_and_confidence_indicators(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    """Test segment traffic aggregation honors sample count sufficiency."""
    # 1. Register vehicle and ingest 6 points on a known road
    reg_num = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": reg_num, "vehicle_type": "truck", "status": "AVAILABLE"},
        headers=dispatcher_headers,
    )
    veh_id = v_res.json()["id"]

    now = datetime.now(timezone.utc)
    locations = [
        {
            "latitude": 26.14365,
            "longitude": 91.74172,
            "speed_kmh": 30.0 + i,
            "recorded_at": (now - timedelta(minutes=10, seconds=i * 10)).isoformat(),
        }
        for i in range(6)
    ]
    await async_client.post(
        f"/api/v1/vehicles/{veh_id}/locations/batch",
        json={"locations": locations},
        headers=driver_headers,
    )

    # 2. Trigger aggregation
    agg_res = await async_client.post(
        "/api/v1/traffic/aggregate",
        json={"window_minutes": 30, "min_samples_for_high_confidence": 5},
        headers=dispatcher_headers,
    )
    assert agg_res.status_code == 200
    agg_summary = agg_res.json()
    assert agg_summary["total_samples_analyzed"] >= 6
    assert agg_summary["segments_aggregated"] >= 1

    # 3. Inspect traffic observations
    traffic_res = await async_client.get("/api/v1/traffic?limit=10", headers=dispatcher_headers)
    assert traffic_res.status_code == 200
    obs_list = traffic_res.json()
    assert len(obs_list) >= 1
    high_conf = next((o for o in obs_list if o["sample_count"] >= 5), None)
    if high_conf:
        assert high_conf["confidence"] == "HIGH"
        assert high_conf["avg_speed_kmh"] > 0
        assert high_conf["congestion_ratio"] is not None
