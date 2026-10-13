"""Storage abstraction for incident photographic evidence."""

import abc
import os
import uuid
from pathlib import Path
from typing import BinaryIO
from fastapi import HTTPException, status
from backend.config import get_settings

settings = get_settings()

# Magic bytes headers for validated image types
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

SAFE_EXTENSIONS_BY_MIME: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def detect_mime_type(content: bytes) -> str | None:
    """Inspects raw file header bytes to reliably determine media type."""
    if len(content) < 12:
        return None

    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"

    return None


class StorageService(abc.ABC):
    """Abstract storage interface allowing local storage now and S3/cloud storage later."""

    @abc.abstractmethod
    async def save_evidence_file(
        self,
        content: bytes,
        original_filename: str,
        incident_id: uuid.UUID,
    ) -> tuple[str, str, int, str]:
        """
        Saves raw file content and returns:
        (stored_filename, storage_ref_url, file_size_bytes, validated_mime_type)
        """
        pass

    @abc.abstractmethod
    async def get_evidence_file(self, stored_filename: str) -> tuple[bytes, str]:
        """Retrieves raw content and mime type for a stored file reference."""
        pass

    @abc.abstractmethod
    async def delete_evidence_file(self, stored_filename: str) -> bool:
        """Deletes stored file."""
        pass


class LocalStorageService(StorageService):
    """Local filesystem storage provider for development and testing."""

    def __init__(self, media_dir: str | None = None, max_size_bytes: int | None = None):
        self.media_dir = Path(media_dir or settings.MEDIA_DIR)
        self.max_size_bytes = max_size_bytes or settings.MAX_UPLOAD_SIZE_BYTES
        self.media_dir.mkdir(parents=True, exist_ok=True)

    async def save_evidence_file(
        self,
        content: bytes,
        original_filename: str,
        incident_id: uuid.UUID,
    ) -> tuple[str, str, int, str]:
        file_size = len(content)
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file upload is not permitted.",
            )

        if file_size > self.max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File size ({file_size} bytes) exceeds maximum permitted limit ({self.max_size_bytes} bytes).",
            )

        # Validate actual magic bytes
        mime_type = detect_mime_type(content)
        if not mime_type or mime_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Unsupported or corrupted image file. Detected mime: '{mime_type}'. "
                    f"Allowed types: {settings.ALLOWED_IMAGE_TYPES}"
                ),
            )

        ext = SAFE_EXTENSIONS_BY_MIME.get(mime_type, "bin")
        # Generate safe server-controlled filename (never use client-provided path)
        unique_token = uuid.uuid4().hex[:12]
        stored_filename = f"{incident_id}_{unique_token}.{ext}"
        target_path = self.media_dir / stored_filename

        try:
            target_path.write_bytes(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist evidence file to storage: {exc}",
            )

        file_url = f"/api/v1/incidents/{incident_id}/evidence/{stored_filename}/download"
        return stored_filename, file_url, file_size, mime_type

    async def get_evidence_file(self, stored_filename: str) -> tuple[bytes, str]:
        # Guard against path traversal attacks
        safe_filename = Path(stored_filename).name
        target_path = self.media_dir / safe_filename

        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence file '{safe_filename}' not found on storage.",
            )

        content = target_path.read_bytes()
        mime_type = detect_mime_type(content) or "application/octet-stream"
        return content, mime_type

    async def delete_evidence_file(self, stored_filename: str) -> bool:
        safe_filename = Path(stored_filename).name
        target_path = self.media_dir / safe_filename
        if target_path.exists():
            target_path.unlink()
            return True
        return False


def get_storage_service() -> StorageService:
    """Factory returning active storage provider."""
    return LocalStorageService()
