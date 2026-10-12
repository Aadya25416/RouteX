"""Tests for Evidence upload, storage abstraction, validation, and retrieval."""

import io
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


# Minimal valid JPEG binary with magic bytes (\xff\xd8\xff)
MOCK_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
    b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)

# Minimal valid PNG binary with magic bytes (\x89PNG\r\n\x1a\n)
MOCK_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_evidence_upload_valid_jpeg(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test valid photographic evidence upload by field officer."""
    # 1. Create incident
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "LANDSLIDE",
            "severity": "HIGH",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert create_res.status_code == 201
    incident_id = create_res.json()["id"]

    # 2. Upload valid JPEG evidence
    files = {"file": ("rockfall_photo.jpg", MOCK_JPEG_BYTES, "image/jpeg")}
    upload_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    assert ev_data["incident_id"] == incident_id
    assert ev_data["original_filename"] == "rockfall_photo.jpg"
    assert ev_data["media_type"] == "image/jpeg"
    assert ev_data["file_size_bytes"] == len(MOCK_JPEG_BYTES)
    assert ev_data["processing_status"] == "PENDING"
    assert ev_data["stored_filename"].endswith(".jpg")
    evidence_id = ev_data["id"]

    # 3. List evidence metadata
    list_res = await async_client.get(
        f"/api/v1/incidents/{incident_id}/evidence",
        headers=field_officer_headers,
    )
    assert list_res.status_code == 200
    evidence_list = list_res.json()
    assert len(evidence_list) == 1
    assert evidence_list[0]["id"] == evidence_id

    # 4. Download evidence through protected endpoint
    download_res = await async_client.get(
        f"/api/v1/incidents/{incident_id}/evidence/{evidence_id}/download",
        headers=field_officer_headers,
    )
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "image/jpeg"
    assert download_res.content == MOCK_JPEG_BYTES


@pytest.mark.asyncio
async def test_evidence_download_requires_auth(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test private incident evidence is not publicly accessible without authentication."""
    # Create incident and upload evidence
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "LOW",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = inc_res.json()["id"]
    upload_res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        files={"file": ("damage.png", MOCK_PNG_BYTES, "image/png")},
        headers=field_officer_headers,
    )
    ev_id = upload_res.json()["id"]

    # Attempt to download without authentication headers -> 401 Unauthorized
    unauth_res = await async_client.get(
        f"/api/v1/incidents/{inc_id}/evidence/{ev_id}/download"
    )
    assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_evidence_upload_unsupported_file_type(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test uploading unsupported media (e.g. text or pdf) is rejected."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "OTHER",
            "severity": "LOW",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = inc_res.json()["id"]

    # Text content disguised as image or raw text
    files = {"file": ("report.txt", b"plain text content not an image", "text/plain")}
    res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_evidence_upload_corrupt_magic_bytes(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test spoofed Content-Type header with corrupt/invalid magic bytes is rejected."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "FLOOD",
            "severity": "LOW",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = inc_res.json()["id"]

    # Corrupt bytes claiming to be JPEG
    fake_jpeg = b"NOT_A_JPEG_FILE_HEADER_BINARY"
    files = {"file": ("fake.jpg", fake_jpeg, "image/jpeg")}
    res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_evidence_upload_oversized_file(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test oversized file exceeding max upload size is rejected."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "FLOOD",
            "severity": "LOW",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = inc_res.json()["id"]

    # 16 MB payload (exceeds 15MB limit)
    oversized = MOCK_JPEG_BYTES + (b"\x00" * (16 * 1024 * 1024))
    files = {"file": ("huge.jpg", oversized, "image/jpeg")}
    res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_evidence_path_traversal_sanitization(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test malicious path traversal in filename is sanitized and server-controlled."""
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "LANDSLIDE",
            "severity": "MEDIUM",
            "latitude": 26.14,
            "longitude": 91.74,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = inc_res.json()["id"]

    # Attempt path traversal in client filename
    malicious_filename = "../../../etc/passwd.jpg"
    files = {"file": (malicious_filename, MOCK_JPEG_BYTES, "image/jpeg")}
    res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        files=files,
        headers=field_officer_headers,
    )
    assert res.status_code == 201
    data = res.json()
    # Stored filename must NEVER contain ../
    assert ".." not in data["stored_filename"]
    assert "/" not in data["stored_filename"]
