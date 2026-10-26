import os
import re
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.storage.base import (
    BaseStorageProvider,
    StorageError,
    StorageObjectNotFoundError,
    StorageConfigurationError,
)
from app.services.storage.local import LocalStorageProvider
from app.services.storage.s3 import S3StorageProvider

logger = logging.getLogger("cogniva.storage.service")

MAGIC_SIGNATURES = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # Standard ZIP / OpenXML archive header
}


class StorageService:
    """
    Central storage coordination service for Cogniva.
    Coordinates tenant-isolated file validation, magic byte verification,
    durable cloud object storage (S3 / Cloudflare R2 / MinIO), local ephemeral caching,
    short-lived presigned download URLs, and lifecycle deletion.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.STORAGE_DIR).resolve()
        self.documents_dir = self.base_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

        self._local_provider = LocalStorageProvider(base_dir=str(self.base_dir))
        self._provider: BaseStorageProvider = self._initialize_default_provider()

    def _initialize_default_provider(self) -> BaseStorageProvider:
        """
        Initializes provider based on environment configuration.
        Defaults to S3/R2 if credentials and bucket are configured, otherwise LocalStorageProvider.
        """
        provider_type = (settings.STORAGE_PROVIDER or "local").lower().strip()

        if provider_type in ("s3", "r2") or settings.S3_BUCKET_NAME:
            try:
                logger.info(f"Initializing durable S3/R2 object storage provider (bucket: {settings.S3_BUCKET_NAME})")
                return S3StorageProvider(
                    bucket_name=settings.S3_BUCKET_NAME,
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    region_name=settings.S3_REGION_NAME,
                    access_key_id=settings.S3_ACCESS_KEY_ID,
                    secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    prefix=settings.S3_PREFIX,
                )
            except Exception as e:
                logger.warning(
                    f"Could not initialize S3StorageProvider ({e}). "
                    "Falling back to LocalStorageProvider. Configure S3_BUCKET_NAME to enable durable cloud storage."
                )
                return self._local_provider
        return self._local_provider

    @property
    def provider(self) -> BaseStorageProvider:
        return self._provider

    def set_provider(self, provider: BaseStorageProvider) -> None:
        """Allows runtime provider injection (e.g. for testing with mock or specific bucket)."""
        self._provider = provider

    def reset_default_provider(self) -> None:
        """Resets provider to environment default."""
        self._provider = self._initialize_default_provider()

    def get_user_storage_dir(self, user_id: uuid.UUID) -> Path:
        """Guarantees existence of user-isolated storage directory on local disk."""
        user_dir = (self.documents_dir / str(user_id)).resolve()
        if not str(user_dir).startswith(str(self.documents_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path specification."
            )
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes original filename to prevent path traversal and shell injection."""
        clean_name = os.path.basename(filename)
        clean_name = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', clean_name).strip()
        if not clean_name:
            clean_name = f"document_{uuid.uuid4().hex[:8]}"
        return clean_name

    def validate_file_metadata(self, filename: str) -> str:
        """Validates file extension against allowed formats."""
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format. Uploaded file must have an extension (.pdf, .docx, or .csv)."
            )

        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(f".{e}" for e in settings.ALLOWED_EXTENSIONS)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type '{ext}'. Supported formats: {allowed}"
            )
        return ext

    def validate_magic_bytes(self, header: bytes, file_type: str) -> None:
        """Validates magic bytes to ensure file contents match claimed MIME type."""
        if not header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded. Please upload a valid document."
            )

        if file_type == "csv":
            if b"\x00" in header:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid CSV format: binary content detected."
                )
            return

        signatures = MAGIC_SIGNATURES.get(file_type, [])
        is_valid = any(header.startswith(sig) for sig in signatures)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file content for .{file_type} format. The file header does not match expected format specifications."
            )

    async def save_uploaded_file(
        self,
        file: UploadFile,
        user_id: uuid.UUID,
        document_id: Optional[uuid.UUID] = None,
    ) -> Tuple[str, str, str, int, str, Dict[str, Any]]:
        """
        Validates uploaded file, streams bytes to durable object storage (or local disk),
        and caches locally for immediate extraction.
        """
        doc_id = document_id or uuid.uuid4()
        original_name = self.sanitize_filename(file.filename or "uploaded_file")
        file_type = self.validate_file_metadata(original_name)

        user_dir = self.get_user_storage_dir(user_id)

        # Read initial chunk for magic bytes inspection
        initial_chunk = await file.read(1024)
        if not initial_chunk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        self.validate_magic_bytes(initial_chunk, file_type)

        storage_id = uuid.uuid4().hex
        stored_filename = f"{storage_id}.{file_type}"
        local_target_path = user_dir / stored_filename

        max_size = settings.max_upload_size_bytes
        total_bytes = len(initial_chunk)

        # Stream into bytearray / file while checking max size
        content_parts = [initial_chunk]
        chunk_size = 64 * 1024

        try:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                    )
                content_parts.append(chunk)

            full_content = b"".join(content_parts)

            # 1. Save local ephemeral copy for immediate extraction pipeline
            with open(local_target_path, "wb") as f:
                f.write(full_content)

            # 2. Persist to active storage provider (Durable S3/R2 or Local)
            content_type = file.content_type or f"application/{file_type}"
            provider_meta = await self._provider.store_object(
                user_id=user_id,
                document_id=doc_id,
                filename=stored_filename,
                content=full_content,
                content_type=content_type,
            )

            storage_key = provider_meta.get("storage_key") or f"documents/{user_id}/{stored_filename}"

            metadata = {
                "size_bytes": total_bytes,
                "content_type": content_type,
                "original_filename": original_name,
                "stored_filename": stored_filename,
                "storage_provider": self._provider.provider_name,
                "storage_key": storage_key,
                "durable": self._provider.is_durable,
                "etag": provider_meta.get("etag"),
            }

            return stored_filename, original_name, file_type, total_bytes, storage_key, metadata

        except Exception:
            # Clean up partial local file
            if local_target_path.exists():
                try:
                    local_target_path.unlink()
                except OSError:
                    pass
            raise

    def get_full_path(self, relative_path: str) -> Path:
        """Resolves absolute path on local filesystem."""
        return (self.base_dir / relative_path).resolve()

    async def get_document_bytes(
        self,
        user_id: uuid.UUID,
        storage_path: str,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Retrieves authentic document bytes.
        If local file is missing (e.g. after ephemeral container restart),
        transparently retrieves from durable object storage provider and caches locally.
        """
        meta = dict(metadata_ or {})
        storage_key = meta.get("storage_key") or storage_path

        # 1. Check local ephemeral cache
        local_path = self.get_full_path(storage_path)
        if local_path.exists() and local_path.is_file():
            with open(local_path, "rb") as f:
                return f.read()

        # 2. Retrieve from active storage provider (e.g. S3 / R2)
        try:
            bytes_data = await self._provider.retrieve_object(user_id, storage_key)
            # Cache locally to speed up subsequent reads in same container lifecycle
            try:
                user_dir = self.get_user_storage_dir(user_id)
                cache_file = user_dir / Path(storage_key).name
                with open(cache_file, "wb") as f:
                    f.write(bytes_data)
            except Exception as e:
                logger.warning(f"Could not cache retrieved object locally: {e}")
            return bytes_data
        except StorageObjectNotFoundError:
            # Also check local provider as fallback
            if self._provider != self._local_provider:
                try:
                    return await self._local_provider.retrieve_object(user_id, storage_key)
                except Exception:
                    pass
            raise StorageObjectNotFoundError(
                f"Document content for key '{storage_key}' could not be found in durable storage or local cache."
            )

    async def generate_download_url(
        self,
        user_id: uuid.UUID,
        storage_path: str,
        original_filename: str,
        metadata_: Optional[Dict[str, Any]] = None,
        expiration_seconds: int = 900,
    ) -> Optional[str]:
        """
        Generates short-lived presigned download URL if backed by S3/R2.
        Returns None for local storage.
        """
        meta = dict(metadata_ or {})
        storage_key = meta.get("storage_key") or storage_path
        return await self._provider.generate_presigned_url(
            user_id=user_id,
            storage_key=storage_key,
            original_filename=original_filename,
            expiration_seconds=expiration_seconds,
        )

    def delete_stored_file(
        self,
        user_id: uuid.UUID,
        relative_storage_path: str,
    ) -> bool:
        """Synchronously cleans up local ephemeral file."""
        full_path = self.get_full_path(relative_storage_path)
        user_dir = self.get_user_storage_dir(user_id)

        if not str(full_path).startswith(str(user_dir)):
            return False

        deleted = False
        if full_path.exists() and full_path.is_file():
            try:
                full_path.unlink()
                deleted = True
            except OSError:
                pass

        json_path = full_path.with_name(f"{full_path.stem}_extracted.json")
        if json_path.exists() and json_path.is_file():
            try:
                json_path.unlink()
            except OSError:
                pass

        return deleted

    async def delete_document_completely(
        self,
        user_id: uuid.UUID,
        storage_path: str,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Asynchronously and idempotently purges the document from both
        durable object storage (S3/R2) and local ephemeral cache.
        """
        meta = dict(metadata_ or {})
        storage_key = meta.get("storage_key") or storage_path

        # 1. Delete from remote object storage
        provider_deleted = False
        try:
            provider_deleted = await self._provider.delete_object(user_id, storage_key)
        except Exception as e:
            logger.warning(f"Error deleting object from provider: {e}")

        # 2. Delete from local disk
        local_deleted = self.delete_stored_file(user_id, storage_path)

        return provider_deleted or local_deleted

    def save_extracted_json(
        self,
        user_id: uuid.UUID,
        relative_storage_path: str,
        data: Dict[str, Any]
    ) -> str:
        """Saves extracted JSON artifact safely in the user's storage directory."""
        full_path = self.get_full_path(relative_storage_path)
        user_dir = self.get_user_storage_dir(user_id)
        if not str(full_path).startswith(str(user_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path."
            )

        json_path = full_path.with_name(f"{full_path.stem}_extracted.json")
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return f"documents/{user_id}/{json_path.name}"

    def load_extracted_json(
        self,
        user_id: uuid.UUID,
        relative_json_path: str
    ) -> Optional[Dict[str, Any]]:
        """Loads extracted JSON artifact with tenant containment verification."""
        full_path = self.get_full_path(relative_json_path)
        user_dir = self.get_user_storage_dir(user_id)
        if not str(full_path).startswith(str(user_dir)):
            return None

        if not full_path.exists() or not full_path.is_file():
            return None

        import json
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)


# Singleton instance
storage_service = StorageService()
