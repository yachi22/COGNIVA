import logging
import uuid
from typing import Any, Dict, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.storage.base import (
    BaseStorageProvider,
    StorageObjectNotFoundError,
    StorageConfigurationError,
)

logger = logging.getLogger("cogniva.storage.s3")


class S3StorageProvider(BaseStorageProvider):
    """
    Durable object storage provider compatible with AWS S3, Cloudflare R2, and MinIO.
    Enforces strict tenant isolation in object keys:
    `{prefix}/tenants/{user_id}/documents/{document_id}/{filename}`
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        prefix: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.region_name = region_name or settings.S3_REGION_NAME or "us-east-1"
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self.prefix = (prefix or settings.S3_PREFIX or "cogniva").strip("/")

        if not self.bucket_name:
            raise StorageConfigurationError(
                "S3_BUCKET_NAME is required for S3/R2 durable object storage provider."
            )

        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region_name,
            "config": Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        try:
            self._s3_client = boto3.client(**client_kwargs)
        except Exception as e:
            raise StorageConfigurationError(f"Failed to initialize S3 client: {str(e)}")

    @property
    def provider_name(self) -> str:
        if self.endpoint_url and "r2.cloudflarestorage.com" in self.endpoint_url:
            return "r2"
        return "s3"

    @property
    def is_durable(self) -> bool:
        return True

    def build_object_key(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
    ) -> str:
        """
        Constructs deterministic, tenant-partitioned object key.
        cogniva/tenants/<user-id>/documents/<doc-id>/<filename>
        """
        clean_filename = filename.replace("\\", "/").split("/")[-1]
        parts = [self.prefix, "tenants", str(user_id), "documents", str(document_id), clean_filename]
        return "/".join(p for p in parts if p)

    def _verify_tenant_ownership(self, user_id: uuid.UUID, storage_key: str) -> None:
        """
        Guarantees that a requested storage_key contains the user's UUID path segment.
        Prevents cross-tenant retrieval even if key was manipulated.
        """
        expected_segment = f"tenants/{str(user_id)}/"
        if expected_segment not in storage_key and not storage_key.startswith(f"documents/{str(user_id)}/"):
            raise StorageObjectNotFoundError(f"Access denied: storage key does not belong to tenant {user_id}")

    async def store_object(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> Dict[str, Any]:
        storage_key = self.build_object_key(user_id, document_id, filename)

        try:
            response = self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "tenant_id": str(user_id),
                    "document_id": str(document_id),
                    "original_filename": filename,
                },
            )
            etag = response.get("ETag", "").strip('"')
            logger.info(f"Durable object stored: s3://{self.bucket_name}/{storage_key} ({len(content)} bytes)")
            return {
                "storage_provider": self.provider_name,
                "s3_bucket": self.bucket_name,
                "storage_key": storage_key,
                "size_bytes": len(content),
                "durable": True,
                "content_type": content_type,
                "etag": etag,
            }
        except ClientError as e:
            logger.error(f"S3 put_object failed for key '{storage_key}': {str(e)}", exc_info=True)
            raise StorageError(f"Failed to persist object in durable storage: {str(e)}")

    async def retrieve_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bytes:
        self._verify_tenant_ownership(user_id, storage_key)

        try:
            response = self._s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return response["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise StorageObjectNotFoundError(f"Object '{storage_key}' not found in bucket '{self.bucket_name}'.")
            logger.error(f"S3 get_object failed: {str(e)}", exc_info=True)
            raise StorageError(f"Failed to retrieve object from storage: {str(e)}")

    async def generate_presigned_url(
        self,
        user_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        expiration_seconds: int = 900,
    ) -> Optional[str]:
        self._verify_tenant_ownership(user_id, storage_key)

        try:
            safe_download_name = original_filename.replace('"', "")
            url = self._s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": storage_key,
                    "ResponseContentDisposition": f'attachment; filename="{safe_download_name}"',
                },
                ExpiresIn=expiration_seconds,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for '{storage_key}': {str(e)}")
            return None

    async def delete_object(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        self._verify_tenant_ownership(user_id, storage_key)

        try:
            self._s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            logger.info(f"Durable object deleted: s3://{self.bucket_name}/{storage_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete_object failed for '{storage_key}': {str(e)}")
            return False

    async def object_exists(
        self,
        user_id: uuid.UUID,
        storage_key: str,
    ) -> bool:
        try:
            self._verify_tenant_ownership(user_id, storage_key)
            self._s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return True
        except (ClientError, StorageObjectNotFoundError):
            return False
