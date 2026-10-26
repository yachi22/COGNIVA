import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from app.core.config import settings
from app.services.storage.base import BaseStorageProvider, StorageObjectNotFoundError


class LocalStorageProvider(BaseStorageProvider):
    """
    Local filesystem storage provider.
    Stores files in `storage/documents/<user_id>/` with path traversal protections.
    Suitable for local development and non-durable testing environments.
    """

    def __init__(self, base_dir: Optional[str] = None):
        raw_dir = base_dir or settings.STORAGE_DIR
        self.base_dir = Path(raw_dir).resolve()
        self.documents_dir = self.base_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def is_durable(self) -> bool:
        return False

    def _get_user_dir(self, user_id: uuid.UUID) -> Path:
        user_dir = (self.documents_dir / str(user_id)).resolve()
        if not str(user_dir).startswith(str(self.documents_dir)):
            raise ValueError("Invalid user directory path.")
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _resolve_path(self, user_id: uuid.UUID, storage_key: str) -> Path:
        user_dir = self._get_user_dir(user_id)
        # Normalize key relative to base_dir or user_dir
        cleaned_key = storage_key.replace("\\", "/").strip("/")
        full_path = (self.base_dir / cleaned_key).resolve()
        if not str(full_path).startswith(str(user_dir)):
            # Fallback check if key was just filename
            full_path = (user_dir / Path(cleaned_key).name).resolve()
            if not str(full_path).startswith(str(user_dir)):
                raise StorageObjectNotFoundError(f"Access denied for storage key: {storage_key}")
        return full_path

    async def store_object(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> Dict[str, Any]:
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / filename
        with open(target_path, "wb") as f:
            f.write(content)

        relative_key = f"documents/{user_id}/{filename}"
        return {
            "storage_provider": "local",
            "storage_key": relative_key,
            "size_bytes": len(content),
            "durable": False,
            "content_type": content_type,
            "local_path": str(target_path),
        }

    async def retrieve_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bytes:
        target_path = self._resolve_path(user_id, storage_key)
        if not target_path.exists() or not target_path.is_file():
            raise StorageObjectNotFoundError(
                f"Document binary '{storage_key}' not found on local disk. (Ephemeral disk may have been reset)."
            )
        with open(target_path, "rb") as f:
            return f.read()

    async def generate_presigned_url(
        self,
        user_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        expiration_seconds: int = 900,
    ) -> Optional[str]:
        # Presigned URLs are an object storage feature (S3/R2); local files stream directly
        return None

    async def delete_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        try:
            target_path = self._resolve_path(user_id, storage_key)
            if target_path.exists() and target_path.is_file():
                target_path.unlink()
                return True
        except (StorageObjectNotFoundError, OSError):
            pass
        return False

    async def object_exists(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        try:
            target_path = self._resolve_path(user_id, storage_key)
            return target_path.exists() and target_path.is_file()
        except Exception:
            return False
