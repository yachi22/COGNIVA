import abc
import uuid
from typing import Any, Dict, Optional


class StorageError(Exception):
    """Base exception for storage operations in Cogniva."""
    pass


class StorageObjectNotFoundError(StorageError):
    """Raised when a requested storage object is not found in object storage or disk."""
    pass


class StorageConfigurationError(StorageError):
    """Raised when storage configuration or bucket credentials are missing or invalid."""
    pass


class StoragePayloadTooLargeError(StorageError):
    """Raised when upload exceeds configured maximum payload size."""
    pass


class BaseStorageProvider(abc.ABC):
    """
    Abstract interface for tenant-isolated document storage providers.
    Supports local ephemeral disk storage and durable cloud object stores (AWS S3, Cloudflare R2, MinIO).
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider identifier: 'local', 's3', 'r2', etc."""
        pass

    @property
    @abc.abstractmethod
    def is_durable(self) -> bool:
        """Indicates whether this provider writes to durable persistent object storage."""
        pass

    @abc.abstractmethod
    async def store_object(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> Dict[str, Any]:
        """
        Persists document bytes in tenant-isolated container partition.
        Returns a dictionary containing storage metadata (storage_key, size_bytes, durable, etag).
        """
        pass

    @abc.abstractmethod
    async def retrieve_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bytes:
        """
        Retrieves raw object bytes from storage.
        Raises StorageObjectNotFoundError if object does not exist.
        """
        pass

    @abc.abstractmethod
    async def generate_presigned_url(
        self,
        user_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        expiration_seconds: int = 900,
    ) -> Optional[str]:
        """
        Generates a short-lived presigned download URL with Content-Disposition attachment.
        Returns None if presigned URLs are not supported by the provider.
        """
        pass

    @abc.abstractmethod
    async def delete_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        """
        Deletes object from storage partition.
        Must be idempotent: returns True if deleted, False if already absent.
        """
        pass

    @abc.abstractmethod
    async def object_exists(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        """Checks whether the object exists in storage."""
        pass
