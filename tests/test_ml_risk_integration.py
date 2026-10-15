"""Tests for ML Risk Scoring Integration, Evidence Worker, and Road Risk APIs."""

import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.incidents import (
    AssessedImpact,
    Incident,
    IncidentEvidence,
    IncidentRoadAssociation,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from backend.models.risk import RiskPrediction
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus
from backend.schemas.ml import MLResultSubmissionRequest
from backend.services.evidence_service import EvidenceService
from backend.services.evidence_worker import EvidenceWorker
from backend.services.risk_service import RiskService
from ml.inference.yolo_worker import YOLORoadDamageWorker

settings = get_settings()

MOCK_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
    b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)

CORRUPT_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x00\x00\x00\x00\x00truncated_corrupt_data"


@pytest_asyncio.fixture(autouse=True)
async def seed_ml_test_road(db_session: AsyncSession):
    """Seed sample road segment and node for ML integration tests."""
    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'ml_test_node_%';"))
    await db_session.commit()

    n1 = RoadNode(
        id="ml_test_node_1",
        osm_node_id=8801,
        geom="SRID=4326;POINT(91.7500 26.1850)",
        longitude=91.7500,
        latitude=26.1850,
    )
    n2 = RoadNode(
        id="ml_test_node_2",
        osm_node_id=8802,
        geom="SRID=4326;POINT(91.7520 26.1870)",
        longitude=91.7520,
        latitude=26.1870,
    )
    db_session.add_all([n1, n2])
    await db_session.flush()

    segment = RoadSegment(
        id="ml_test_segment_1",
        osm_way_id=98801,
        u_node_id="ml_test_node_1",
        v_node_id="ml_test_node_2",
        key=0,
        geom="SRID=4326;LINESTRING(91.7500 26.1850, 91.7520 26.1870)",
        length_m=500.0,
        base_speed_kmh=50.0,
        base_travel_time_s=36.0,
        road_class="primary",
        name="Guwahati Sector 1 Road",
        oneway=False,
        access_allowed=True,
        corridor_name="Guwahati-Shillong",
    )
    db_session.add(segment)

    # Initial state: UNKNOWN
    state = RoadSegmentState(
        road_segment_id="ml_test_segment_1",
        status=RoadStatus.UNKNOWN.value,
        safety_score=100.0,
        disruption_probability=None,
        score_confidence=None,
        score_model_version=None,
        score_updated_at=None,
        score_valid_until=None,
        status_reason_codes=["INITIAL_UNKNOWN_SEED"],
    )
    db_session.add(state)
    await db_session.commit()

    yield segment

    # Cleanup
    await db_session.execute(text("DELETE FROM risk_predictions WHERE road_segment_id = 'ml_test_segment_1';"))
    await db_session.execute(text("DELETE FROM incident_road_associations WHERE road_segment_id = 'ml_test_segment_1';"))
    await db_session.execute(text("DELETE FROM road_segment_state WHERE road_segment_id = 'ml_test_segment_1';"))
    await db_session.execute(text("DELETE FROM road_segments WHERE id = 'ml_test_segment_1';"))
    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'ml_test_node_%';"))
    await db_session.commit()


# -----------------------------------------------------------------------------
# 1. Evidence Worker & Inference Pipeline Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_claim_and_process_success(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    ml_service_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Worker claims eligible pending evidence, processes detection, and submits result."""
    # 1. Create incident and upload evidence
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "MEDIUM",
            "latitude": 26.1850,
            "longitude": 91.7500,
            "description": "Crack observed on asphalt",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert inc_res.status_code == 201
    incident_id = inc_res.json()["id"]

    files = {"file": ("crack.jpg", MOCK_JPEG_BYTES, "image/jpeg")}
    up_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert up_res.status_code == 201
    evidence_id = uuid.UUID(up_res.json()["id"])

    # Associate road segment with evidence
    ev = await db_session.get(IncidentEvidence, evidence_id)
    assert ev is not None
    ev.road_segment_id = "ml_test_segment_1"
    await db_session.commit()

    # 2. Worker mock YOLO execution
    mock_yolo = MagicMock(spec=YOLORoadDamageWorker)
    mock_yolo.detect_damage.return_value = {
        "status": "COMPLETED",
        "detection_class": "alligator_crack",
        "confidence": 0.88,
        "metadata": {
            "model_version": "1.0.0",
            "inference_time_ms": 42.5,
            "detections": [
                {
                    "class_name": "alligator_crack",
                    "class_id": 3,
                    "confidence": 0.88,
                    "box": [10.0, 10.0, 120.0, 150.0],
                }
            ],
        },
    }

    worker = EvidenceWorker(worker_id="test_worker_alpha", yolo_worker=mock_yolo)
    processed = await worker.process_task(evidence_id=evidence_id, session=db_session)
    assert processed is not None
    assert processed.processing_status == "COMPLETED"
    assert processed.model_detection_class == "alligator_crack"
    assert processed.model_confidence == 0.88
    assert processed.model_metadata["model_version"] == "1.0.0"

    # Verify road risk re-evaluation was triggered and persisted
    pred_res = await db_session.execute(
        select(RiskPrediction).where(RiskPrediction.road_segment_id == "ml_test_segment_1")
    )
    persisted_preds = pred_res.scalars().all()
    assert len(persisted_preds) >= 1
    latest_pred = persisted_preds[-1]
    assert latest_pred.model_name == "xgboost_unified_pipeline"
    assert latest_pred.model_version == "1.1.0"
    assert 0.0 <= latest_pred.disruption_probability <= 1.0
    assert 0.0 <= latest_pred.safety_score <= 100.0


@pytest.mark.asyncio
async def test_worker_duplicate_claims_prevented(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    ml_service_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Second worker attempting to claim active lease is rejected with 409 Conflict."""
    # 1. Create evidence
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "LANDSLIDE",
            "severity": "HIGH",
            "latitude": 26.1850,
            "longitude": 91.7500,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert inc_res.status_code == 201
    incident_id = inc_res.json()["id"]

    files = {"file": ("slide.jpg", MOCK_JPEG_BYTES, "image/jpeg")}
    up_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert up_res.status_code == 201
    evidence_id = up_res.json()["id"]

    # 2. Worker 1 claims task successfully
    claim1_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/claim",
        json={"worker_id": "worker_node_1"},
        headers=ml_service_headers,
    )
    assert claim1_res.status_code == 200
    assert claim1_res.json()["processing_status"] == "IN_PROGRESS"
    assert claim1_res.json()["claimed_by"] == "worker_node_1"

    # 3. Worker 2 attempts concurrent claim on active lease -> 409 Conflict
    claim2_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/claim",
        json={"worker_id": "worker_node_2"},
        headers=ml_service_headers,
    )
    assert claim2_res.status_code == 409
    assert "actively claimed" in claim2_res.json()["detail"]


@pytest.mark.asyncio
async def test_worker_corrupt_image_marks_failed(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Corrupt image is handled gracefully without crashing; marked as FAILED with bounded retry limit."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "LOW",
            "latitude": 26.1850,
            "longitude": 91.7500,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert inc_res.status_code == 201
    incident_id = inc_res.json()["id"]

    # Upload corrupt image (valid JPEG header magic bytes to pass MIME validation, but corrupt payload)
    files = {"file": ("corrupt.jpg", CORRUPT_JPEG_BYTES, "image/jpeg")}
    up_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert up_res.status_code == 201
    evidence_id = uuid.UUID(up_res.json()["id"])

    # Execute real YOLORoadDamageWorker on corrupt bytes
    worker = EvidenceWorker(worker_id="test_worker_corrupt")
    processed = await worker.process_task(evidence_id=evidence_id, session=db_session)

    assert processed is not None
    assert processed.processing_status == "FAILED"
    assert "unreadable image" in (processed.processing_error or "").lower()


@pytest.mark.asyncio
async def test_result_submission_idempotency(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    ml_service_headers: dict[str, str],
):
    """Submitting inference result repeatedly is idempotent and does not error."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "LOW",
            "latitude": 26.1850,
            "longitude": 91.7500,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert inc_res.status_code == 201
    incident_id = inc_res.json()["id"]

    files = {"file": ("pothole.jpg", MOCK_JPEG_BYTES, "image/jpeg")}
    up_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert up_res.status_code == 201
    evidence_id = up_res.json()["id"]

    # Claim
    claim_res = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/claim",
        json={"worker_id": "worker_idempotent"},
        headers=ml_service_headers,
    )
    assert claim_res.status_code == 200

    # First submit
    res1 = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/result",
        json={
            "worker_id": "worker_idempotent",
            "status": "COMPLETED",
            "model_detection_class": "pothole",
            "model_confidence": 0.92,
            "model_metadata": {"model_version": "1.0.0"},
        },
        headers=ml_service_headers,
    )
    assert res1.status_code == 200
    assert res1.json()["processing_status"] == "COMPLETED"

    # Second submit (identical payload retry)
    res2 = await async_client.post(
        f"/api/v1/ml/evidence/{evidence_id}/result",
        json={
            "worker_id": "worker_idempotent",
            "status": "COMPLETED",
            "model_detection_class": "pothole",
            "model_confidence": 0.92,
            "model_metadata": {"model_version": "1.0.0"},
        },
        headers=ml_service_headers,
    )
    assert res2.status_code == 200
    assert res2.json()["processing_status"] == "COMPLETED"
    assert res2.json()["model_detection_class"] == "pothole"


# -----------------------------------------------------------------------------
# 2. Safety Semantics & Authoritative Precedence Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authoritative_closure_cannot_be_overridden_by_ml(
    db_session: AsyncSession,
):
    """
    CRITICAL SAFETY REQUIREMENT:
    Even if ML predicts high safety score (e.g. 95) and low disruption prob (e.g. 0.05),
    an authoritative confirmed BLOCKED incident must control: status remains BLOCKED,
    safety_score is 0.0, disruption_probability is 1.0.
    """
    risk_service = RiskService(db_session)

    # 1. Create confirmed incident blocking ml_test_segment_1
    incident_id = uuid.uuid4()
    incident = Incident(
        id=incident_id,
        incident_type=IncidentType.LANDSLIDE.value,
        severity=IncidentSeverity.CRITICAL.value,
        status=IncidentStatus.CONFIRMED.value,
        geom="SRID=4326;POINT(91.7500 26.1850)",
        observed_at=datetime.now(timezone.utc),
    )
    assoc = IncidentRoadAssociation(
        incident_id=incident_id,
        road_segment_id="ml_test_segment_1",
        assessed_impact=AssessedImpact.BLOCKED.value,
    )
    db_session.add(incident)
    db_session.add(assoc)
    await db_session.commit()

    # 2. Execute risk evaluation on segment
    pred = await risk_service.evaluate_segment_risk(road_segment_id="ml_test_segment_1")
    assert pred is not None

    # 3. Verify RoadSegmentState enforces BLOCKED precedence
    st_res = await db_session.execute(
        select(RoadSegmentState).where(RoadSegmentState.road_segment_id == "ml_test_segment_1")
    )
    road_state = st_res.scalar_one()

    assert road_state.status == RoadStatus.BLOCKED.value
    assert road_state.safety_score == 0.0
    assert road_state.disruption_probability == 1.0
    assert "AUTHORITATIVE_CONFIRMED_BLOCKAGE" in road_state.status_reason_codes

    risk_service.close()


@pytest.mark.asyncio
async def test_unknown_segment_id_rejected_safely(
    db_session: AsyncSession,
):
    """Non-existent segment ID raises 404 without corrupting database state."""
    risk_service = RiskService(db_session)
    with pytest.raises(Exception) as excinfo:
        await risk_service.evaluate_segment_risk(road_segment_id="non_existent_segment_xyz")
    assert "404" in str(excinfo.value) or "not found" in str(excinfo.value).lower()
    risk_service.close()


# -----------------------------------------------------------------------------
# 3. GET /api/v1/risk Endpoint & Schema Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_risk_unauthenticated_rejected(async_client: AsyncClient):
    """Unauthenticated access to GET /api/v1/risk returns 401 Unauthorized."""
    res = await async_client.get("/api/v1/risk")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_risk_bounded_bbox_filtering(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
):
    """GET /api/v1/risk filters correctly by spatial bounding box."""
    # Tight bounding box directly surrounding ml_test_segment_1 (lat 26.185, lon 91.750)
    res = await async_client.get(
        "/api/v1/risk",
        params={
            "min_lat": 26.184,
            "min_lon": 91.749,
            "max_lat": 26.188,
            "max_lon": 91.753,
            "limit": 50,
        },
        headers=driver_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    matched = [item for item in data["items"] if item["road_segment_id"] == "ml_test_segment_1"]
    assert len(matched) == 1
    assert matched[0]["road_segment_id"] == "ml_test_segment_1"

    # Disjoint bounding box (e.g. Tawang area)
    res_disjoint = await async_client.get(
        "/api/v1/risk",
        params={
            "min_lat": 27.50,
            "min_lon": 92.00,
            "max_lat": 27.60,
            "max_lon": 92.10,
        },
        headers=driver_headers,
    )
    assert res_disjoint.status_code == 200
    disjoint_matched = [item for item in res_disjoint.json()["items"] if item["road_segment_id"] == "ml_test_segment_1"]
    assert len(disjoint_matched) == 0


@pytest.mark.asyncio
async def test_get_risk_invalid_bbox_rejected(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
):
    """Inverted or invalid bounding box coordinates return 400 Bad Request."""
    res = await async_client.get(
        "/api/v1/risk",
        params={
            "min_lat": 26.50,
            "min_lon": 91.80,
            "max_lat": 26.10,  # min_lat > max_lat
            "max_lon": 91.70,
        },
        headers=driver_headers,
    )
    assert res.status_code == 400
    assert "Invalid bounding box" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_risk_unknown_and_stale_semantics(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
):
    """Unassessed segment correctly exposes is_unknown=True and is_stale=True rather than fabricated safety."""
    # Query single segment detail
    res = await async_client.get(
        "/api/v1/risk/ml_test_segment_1",
        headers=driver_headers,
    )
    assert res.status_code == 200
    item = res.json()
    assert item["road_segment_id"] == "ml_test_segment_1"
    assert item["is_unknown"] is True
    assert item["is_stale"] is True
    assert item["score_type"] == "unknown"


@pytest.mark.asyncio
async def test_risk_evaluate_endpoint_rbac_and_execution(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """POST /api/v1/risk/evaluate requires dispatcher/admin and updates risk data."""
    # Driver role cannot trigger evaluation -> 403 Forbidden
    driver_res = await async_client.post(
        "/api/v1/risk/evaluate",
        json={"road_segment_id": "ml_test_segment_1"},
        headers=driver_headers,
    )
    assert driver_res.status_code == 403

    # Dispatcher triggers evaluation -> 200 OK
    eval_res = await async_client.post(
        "/api/v1/risk/evaluate",
        json={"road_segment_id": "ml_test_segment_1"},
        headers=dispatcher_headers,
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["road_segment_id"] == "ml_test_segment_1"
    assert data["is_unknown"] is False
    assert 0.0 <= data["safety_score"] <= 100.0
    assert data["disruption_probability"] is not None
    assert 0.0 <= data["disruption_probability"] <= 1.0
    assert data["model_version"] == "1.1.0"
    assert data["score_type"] in ["ml_probabilistic", "authoritative_incident"]


# -----------------------------------------------------------------------------
# 4. Real-Inference Smoke Test (Separate, Unmocked Model Execution)
# -----------------------------------------------------------------------------

def test_real_model_inference_smoke():
    """
    Local smoke test verifying real model artifacts without mocking:
    - XGBoost landslide risk model (ml/models/xgboost/landslide_risk_xgboost.json)
    - YOLOv8 road-damage model (ml/models/best.pt)
    """
    import os
    from ml.inference.risk_predictor import SegmentRiskPredictor

    # 1. XGBoost Landslide Risk Predictor
    risk_pred = SegmentRiskPredictor()
    assert risk_pred.clf is not None
    res = risk_pred.predict_risk(
        lat=26.185,
        lon=91.750,
        precip_mm=15.0,
        precip_3d_mm=45.0,
        precip_7d_mm=90.0,
        wind_kmh=20.0,
        month=7,
    )
    assert "disruption_probability" in res
    assert "safety_score" in res
    assert 0.0 <= res["disruption_probability"] <= 1.0
    assert 0.0 <= res["safety_score"] <= 100.0
    risk_pred.close()

    # 2. YOLOv8 Road Damage Model
    yolo_weights = os.path.join("ml", "models", "best.pt")
    if os.path.exists(yolo_weights):
        yolo_worker = YOLORoadDamageWorker(weights_file=yolo_weights)
        assert yolo_worker.model is not None
        # Run detection on mock JPEG
        yolo_res = yolo_worker.detect_damage(MOCK_JPEG_BYTES)
        assert yolo_res["status"] in ["COMPLETED", "NO_DETECTIONS"]
        assert "metadata" in yolo_res
