import io
import uuid
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile, status

from app.models.document import Document
from app.models.user import User
from app.services.storage import (
    storage_service,
    LocalStorageProvider,
    S3StorageProvider,
    BaseStorageProvider,
    StorageObjectNotFoundError,
    StorageConfigurationError,
    StorageMigrationService,
)
from app.services.document_service import DocumentService


# 1. Validation & Magic Byte Security Tests
def test_storage_service_format_and_magic_byte_validation():
    # Valid PDF magic bytes pass
    valid_pdf = b"%PDF-1.7\nsome pdf content"
    storage_service.validate_magic_bytes(valid_pdf, "pdf")

    # Valid DOCX magic bytes pass
    valid_docx = b"PK\x03\x04\x14\x00\x06\x00"
    storage_service.validate_magic_bytes(valid_docx, "docx")

    # Valid CSV passes
    valid_csv = b"id,name,role\n1,alice,admin\n"
    storage_service.validate_magic_bytes(valid_csv, "csv")

    # Binary null bytes in CSV rejected with 400
    invalid_csv = b"id,name\x00malicious_binary"
    with pytest.raises(HTTPException) as exc:
        storage_service.validate_magic_bytes(invalid_csv, "csv")
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    # Mismatched PDF header rejected with 400
    fake_pdf = b"NOT_A_PDF_STREAM"
    with pytest.raises(HTTPException) as exc_pdf:
        storage_service.validate_magic_bytes(fake_pdf, "pdf")
    assert exc_pdf.value.status_code == status.HTTP_400_BAD_REQUEST

    # Empty payload rejected with 400
    with pytest.raises(HTTPException) as exc_empty:
        storage_service.validate_magic_bytes(b"", "pdf")
    assert exc_empty.value.status_code == status.HTTP_400_BAD_REQUEST


# 2. Unsupported Extensions and Path Traversal Filename Sanitization
def test_filename_sanitization_and_unsupported_extensions():
    # Path traversal attack stripped
    malicious = "../../../etc/passwd.pdf"
    clean = storage_service.sanitize_filename(malicious)
    assert "/" not in clean and "\\" not in clean
    assert "passwd.pdf" in clean

    # Windows-style path traversal stripped
    win_malicious = "..\\..\\windows\\system32\\cmd.exe.docx"
    win_clean = storage_service.sanitize_filename(win_malicious)
    assert "\\" not in win_clean and "/" not in win_clean
    assert "cmd.exe.docx" in win_clean

    # Unsupported extension rejected
    with pytest.raises(HTTPException) as exc:
        storage_service.validate_file_metadata("malware.exe")
    assert exc.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    # Missing extension rejected
    with pytest.raises(HTTPException) as exc_no_ext:
        storage_service.validate_file_metadata("no_extension_file")
    assert exc_no_ext.value.status_code == status.HTTP_400_BAD_REQUEST


# 3. Local Storage Provider Lifecycle & Path Traversal Prevention
@pytest.mark.asyncio
async def test_local_storage_provider_lifecycle(tmp_path: Path):
    local_provider = LocalStorageProvider(base_dir=str(tmp_path))
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    test_bytes = b"Hello Cogniva Local Storage Content"

    # Store
    meta = await local_provider.store_object(
        user_id=user_id,
        document_id=doc_id,
        filename="test.pdf",
        content=test_bytes,
        content_type="application/pdf",
    )
    assert meta["storage_provider"] == "local"
    assert meta["size_bytes"] == len(test_bytes)
    assert meta["durable"] is False
    storage_key = meta["storage_key"]

    # Exists
    assert await local_provider.object_exists(user_id, storage_key) is True

    # Retrieve
    retrieved = await local_provider.retrieve_object(user_id, storage_key)
    assert retrieved == test_bytes

    # Delete
    deleted = await local_provider.delete_object(user_id, storage_key)
    assert deleted is True
    assert await local_provider.object_exists(user_id, storage_key) is False

    # Second delete is idempotent
    second_delete = await local_provider.delete_object(user_id, storage_key)
    assert second_delete is False

    # Cross-tenant path traversal denied
    attacker_id = uuid.uuid4()
    with pytest.raises(StorageObjectNotFoundError):
        await local_provider.retrieve_object(attacker_id, storage_key)


# 4. S3 / Cloudflare R2 Provider Mocked Lifecycle & Cross-Tenant Defense
@pytest.mark.asyncio
async def test_s3_storage_provider_lifecycle():
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    test_content = b"%PDF-1.5 Grounded Enterprise Intelligence Bytes"

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        # Mock put_object response
        mock_client.put_object.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "ETag": '"abc123etag"',
        }

        # Mock get_object response
        mock_body = MagicMock()
        mock_body.read.return_value = test_content
        mock_client.get_object.return_value = {"Body": mock_body}

        # Mock presigned url
        mock_client.generate_presigned_url.return_value = "https://cogniva-bucket.s3.amazonaws.com/tenants/..."

        s3_provider = S3StorageProvider(
            bucket_name="cogniva-test-bucket",
            region_name="us-east-1",
            access_key_id="mock_key",
            secret_access_key="mock_secret",
            prefix="enterprise",
        )

        assert s3_provider.provider_name == "s3"
        assert s3_provider.is_durable is True

        # 1. Store
        res = await s3_provider.store_object(
            user_id=user_id,
            document_id=doc_id,
            filename="financial_audit.pdf",
            content=test_content,
            content_type="application/pdf",
        )
        assert res["durable"] is True
        assert res["s3_bucket"] == "cogniva-test-bucket"
        assert res["etag"] == "abc123etag"
        expected_key = f"enterprise/tenants/{user_id}/documents/{doc_id}/financial_audit.pdf"
        assert res["storage_key"] == expected_key

        # 2. Retrieve
        retrieved = await s3_provider.retrieve_object(user_id, expected_key)
        assert retrieved == test_content

        # 3. Presigned URL
        url = await s3_provider.generate_presigned_url(user_id, expected_key, "financial_audit.pdf", expiration_seconds=600)
        assert url is not None
        assert url.startswith("https://")

        # 4. Cross-Tenant Denial: Attacker cannot access User's storage key
        attacker_id = uuid.uuid4()
        with pytest.raises(StorageObjectNotFoundError):
            await s3_provider.retrieve_object(attacker_id, expected_key)

        with pytest.raises(StorageObjectNotFoundError):
            await s3_provider.generate_presigned_url(attacker_id, expected_key, "financial_audit.pdf")

        with pytest.raises(StorageObjectNotFoundError):
            await s3_provider.delete_object(attacker_id, expected_key)

        # 5. Delete
        deleted = await s3_provider.delete_object(user_id, expected_key)
        assert deleted is True


# 5. Ephemeral Disk Recovery Across Container Restarts
@pytest.mark.asyncio
async def test_ephemeral_disk_recovery_across_restarts(tmp_path: Path):
    """
    Simulates a container restart:
    1. Local ephemeral storage directory is wiped empty.
    2. Document metadata points to durable storage provider.
    3. StorageService.get_document_bytes restores the file from durable storage and re-caches it locally.
    """
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    original_bytes = b"%PDF-1.4 Durable Policy Content That Survives Restarts"

    # Create mock durable provider
    mock_durable_provider = MagicMock(spec=BaseStorageProvider)
    mock_durable_provider.provider_name = "s3"
    mock_durable_provider.is_durable = True
    mock_durable_provider.retrieve_object = AsyncMock(return_value=original_bytes)

    # Empty base directory (simulating fresh container instance)
    empty_storage = tmp_path / "fresh_container_storage"
    empty_storage.mkdir()

    from app.services.storage.service import StorageService
    svc = StorageService(base_dir=str(empty_storage))
    svc.set_provider(mock_durable_provider)

    storage_key = f"cogniva/tenants/{user_id}/documents/{doc_id}/policy.pdf"
    meta = {
        "storage_provider": "s3",
        "storage_key": storage_key,
        "durable": True,
    }

    # Verify local file is absent before call
    local_path = svc.get_full_path(f"documents/{user_id}/policy.pdf")
    assert not local_path.exists()

    # Call get_document_bytes
    retrieved_bytes = await svc.get_document_bytes(
        user_id=user_id,
        storage_path=f"documents/{user_id}/policy.pdf",
        metadata_=meta,
    )

    # Verifies bytes retrieved from durable provider
    assert retrieved_bytes == original_bytes
    mock_durable_provider.retrieve_object.assert_awaited_once_with(user_id, storage_key)

    # Verifies file was cached locally on disk
    cached_file = svc.get_user_storage_dir(user_id) / "policy.pdf"
    assert cached_file.exists()
    assert cached_file.read_bytes() == original_bytes


# 6. Document Download Tenant Isolation Tests
@pytest.mark.asyncio
async def test_document_download_tenant_isolation():
    doc_svc = DocumentService()
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_db = AsyncMock()
    # Attacker query returns None (not found / not owned)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    # Attacker attempt raises 404
    with pytest.raises(HTTPException) as exc:
        await doc_svc.get_document_download(
            db=mock_db,
            user_id=attacker_id,
            document_id=doc_id,
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc.value.detail.lower()


# 7. Resumable & Idempotent Migration Service Tests
@pytest.mark.asyncio
async def test_storage_migration_service_idempotence_and_safety():
    migration_svc = StorageMigrationService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = "contract.pdf"
    mock_doc.original_filename = "Master_Contract.pdf"
    mock_doc.file_type = "pdf"
    mock_doc.storage_path = f"documents/{user_id}/contract.pdf"
    mock_doc.metadata_ = {
        "durable": True,
        "storage_provider": "s3",
        "storage_key": f"cogniva/tenants/{user_id}/documents/{doc_id}/contract.pdf",
    }

    mock_target = MagicMock(spec=BaseStorageProvider)
    mock_target.provider_name = "s3"

    mock_db = AsyncMock()

    # Document already durable -> skips cleanly without error
    res = await migration_svc.migrate_document(
        db=mock_db,
        document=mock_doc,
        target_provider=mock_target,
    )
    assert res["status"] == "already_durable"
    mock_target.store_object.assert_not_called()


# 8. Missing Ephemeral Binary Migration Preserves DB Chunks
@pytest.mark.asyncio
async def test_missing_binary_migration_preserves_database_records():
    migration_svc = StorageMigrationService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = "lost_binary.docx"
    mock_doc.original_filename = "Lost_Binary.docx"
    mock_doc.file_type = "docx"
    mock_doc.storage_path = f"documents/{user_id}/lost_binary.docx"
    mock_doc.metadata_ = {"durable": False, "storage_provider": "local"}

    mock_local = MagicMock(spec=BaseStorageProvider)
    mock_local.retrieve_object = AsyncMock(side_effect=StorageObjectNotFoundError("File not on disk"))

    mock_target = MagicMock(spec=BaseStorageProvider)
    mock_target.provider_name = "s3"

    mock_db = AsyncMock()

    # Migration encounters missing local file
    res = await migration_svc.migrate_document(
        db=mock_db,
        document=mock_doc,
        target_provider=mock_target,
        local_provider=mock_local,
    )

    # Verifies chunks are intact and missing status is recorded without destroying DB record
    assert res["status"] == "binary_missing_on_ephemeral_disk"
    assert res["chunks_intact"] is True
    assert mock_doc.metadata_["missing_binary_on_ephemeral_disk"] is True
    mock_db.commit.assert_awaited_once()
