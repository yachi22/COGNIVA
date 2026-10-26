import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.storage.base import BaseStorageProvider, StorageError

logger = logging.getLogger("cogniva.storage.migration")


class StorageMigrationService:
    """
    Coordinates safe, idempotent, and resumable migrations of document binaries
    from ephemeral local storage to durable cloud object storage.
    Preserves all database records, embeddings, and vector indices.
    """

    async def migrate_document(
        self,
        db: AsyncSession,
        document: Document,
        target_provider: BaseStorageProvider,
        local_provider: Optional[BaseStorageProvider] = None,
    ) -> Dict[str, Any]:
        """
        Migrates a single document's binary to durable object storage.
        Verifies storage before updating database metadata.
        """
        meta = dict(document.metadata_ or {})

        # 1. Idempotency check: already migrated to target durable provider
        if meta.get("durable") is True and meta.get("storage_provider") == target_provider.provider_name:
            return {
                "document_id": str(document.id),
                "status": "already_durable",
                "storage_key": meta.get("storage_key"),
            }

        # 2. Retrieve existing document bytes
        content: Optional[bytes] = None
        storage_key = meta.get("storage_key") or document.storage_path

        # Attempt retrieval from existing provider or disk
        if local_provider:
            try:
                content = await local_provider.retrieve_object(document.user_id, storage_key)
            except Exception as e:
                logger.warning(f"Could not retrieve from local provider for doc {document.id}: {e}")

        # If not retrieved via local_provider, check raw file path
        if content is None:
            from pathlib import Path
            from app.core.config import settings
            base_dir = Path(settings.STORAGE_DIR).resolve()
            candidates = [
                base_dir / storage_key,
                base_dir / "documents" / str(document.user_id) / document.filename,
                base_dir / "documents" / str(document.user_id) / (document.original_filename or ""),
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    with open(c, "rb") as f:
                        content = f.read()
                    break

        # 3. Handle missing binary on ephemeral disk cleanly
        if content is None:
            logger.warning(
                f"Document binary for {document.id} was not found on ephemeral disk. "
                "Preserving database chunks, extracted text, and vector embeddings without data loss."
            )
            meta["missing_binary_on_ephemeral_disk"] = True
            document.metadata_ = meta
            await db.commit()
            return {
                "document_id": str(document.id),
                "status": "binary_missing_on_ephemeral_disk",
                "chunks_intact": True,
            }

        # 4. Upload to durable target object storage
        content_type = meta.get("content_type", f"application/{document.file_type}")
        store_res = await target_provider.store_object(
            user_id=document.user_id,
            document_id=document.id,
            filename=document.original_filename or document.filename,
            content=content,
            content_type=content_type,
        )

        # 5. Verify object existence in target storage before updating database record
        new_key = store_res["storage_key"]
        exists = await target_provider.object_exists(document.user_id, new_key)
        if not exists:
            raise StorageError(f"Verification check failed for uploaded object '{new_key}'. Migration aborted.")

        # 6. Update database record metadata
        meta.update({
            "durable": True,
            "storage_provider": target_provider.provider_name,
            "storage_key": new_key,
            "migrated_size_bytes": len(content),
            "migrated_etag": store_res.get("etag"),
        })
        document.metadata_ = meta
        await db.commit()
        await db.refresh(document)

        logger.info(f"Successfully migrated document {document.id} to durable storage ({new_key}).")
        return {
            "document_id": str(document.id),
            "status": "migrated_successfully",
            "storage_key": new_key,
            "size_bytes": len(content),
        }

    async def migrate_all_documents(
        self,
        db: AsyncSession,
        target_provider: BaseStorageProvider,
        local_provider: Optional[BaseStorageProvider] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Executes resumable migration across all or user-specific documents.
        """
        stmt = select(Document)
        if user_id:
            stmt = stmt.where(Document.user_id == user_id)

        res = await db.execute(stmt)
        docs: List[Document] = list(res.scalars().all())

        results = {
            "total_documents": len(docs),
            "migrated": 0,
            "already_durable": 0,
            "missing_on_disk": 0,
            "errors": 0,
            "details": [],
        }

        for doc in docs:
            try:
                outcome = await self.migrate_document(
                    db=db,
                    document=doc,
                    target_provider=target_provider,
                    local_provider=local_provider,
                )
                results["details"].append(outcome)
                if outcome["status"] == "migrated_successfully":
                    results["migrated"] += 1
                elif outcome["status"] == "already_durable":
                    results["already_durable"] += 1
                elif outcome["status"] == "binary_missing_on_ephemeral_disk":
                    results["missing_on_disk"] += 1
            except Exception as e:
                logger.error(f"Migration error for document {doc.id}: {str(e)}", exc_info=True)
                results["errors"] += 1
                results["details"].append({
                    "document_id": str(doc.id),
                    "status": "error",
                    "error": str(e),
                })

        return results


storage_migration_service = StorageMigrationService()
