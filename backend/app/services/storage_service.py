"""
Backward-compatible proxy module for app.services.storage.
"""
from app.services.storage import (
    BaseStorageProvider,
    LocalStorageProvider,
    S3StorageProvider,
    StorageService,
    storage_service,
    StorageError,
    StorageObjectNotFoundError,
    StorageConfigurationError,
    StoragePayloadTooLargeError,
    StorageMigrationService,
    storage_migration_service,
)

__all__ = [
    "BaseStorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "StorageService",
    "storage_service",
    "StorageError",
    "StorageObjectNotFoundError",
    "StorageConfigurationError",
    "StoragePayloadTooLargeError",
    "StorageMigrationService",
    "storage_migration_service",
]
