import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import delete, insert, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.collection import Collection, collection_documents
from app.models.document import Document

logger = logging.getLogger("cogniva.collection_service")


class CollectionService:
    """
    Manages tenant collections, workspace categorization, and collection membership.
    Enforces strict user isolation.
    """

    async def create_collection(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        color: str = "#267653",
    ) -> Collection:
        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Collection name cannot be empty.",
            )

        collection = Collection(
            id=uuid.uuid4(),
            user_id=user_id,
            name=clean_name,
            description=description.strip() if description else None,
            color=color,
        )
        db.add(collection)
        await db.commit()
        await db.refresh(collection)
        return collection

    async def list_collections(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(
                Collection,
                func.count(collection_documents.c.document_id).label("doc_count"),
            )
            .outerjoin(collection_documents, Collection.id == collection_documents.c.collection_id)
            .where(Collection.user_id == user_id)
            .group_by(Collection.id)
            .order_by(Collection.created_at.desc())
        )
        res = await db.execute(stmt)
        rows = res.all()

        results = []
        for col, count in rows:
            results.append({
                "id": str(col.id),
                "user_id": str(col.user_id),
                "name": col.name,
                "description": col.description,
                "color": col.color,
                "document_count": count,
                "documents_count": count,
                "created_at": col.created_at.isoformat() if col.created_at else None,
                "updated_at": col.updated_at.isoformat() if col.updated_at else None,
            })
        return results

    async def update_collection(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Collection:
        stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        res = await db.execute(stmt)
        col = res.scalar_one_or_none()

        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Collection name cannot be empty.",
                )
            col.name = clean_name

        if description is not None:
            col.description = description.strip() or None

        if color is not None:
            col.color = color

        await db.commit()
        await db.refresh(col)
        return col

    async def get_collection_detail(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> Dict[str, Any]:
        stmt = (
            select(Collection)
            .where(
                Collection.id == collection_id,
                Collection.user_id == user_id,
            )
            .options(selectinload(Collection.documents))
        )
        res = await db.execute(stmt)
        col = res.scalar_one_or_none()

        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

        return {
            "id": str(col.id),
            "user_id": str(col.user_id),
            "name": col.name,
            "description": col.description,
            "color": col.color,
            "created_at": col.created_at.isoformat() if col.created_at else None,
            "updated_at": col.updated_at.isoformat() if col.updated_at else None,
            "documents_count": len(col.documents),
            "document_count": len(col.documents),
            "documents": [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "original_filename": d.original_filename or d.filename,
                    "file_type": d.file_type,
                    "status": d.status,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in col.documents
            ],
        }

    async def delete_collection(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
    ) -> None:
        stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        res = await db.execute(stmt)
        col = res.scalar_one_or_none()

        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

        await db.delete(col)
        await db.commit()

    async def add_document_to_collection(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        # Verify collection ownership
        col_stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        col_res = await db.execute(col_stmt)
        if not col_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

        # Verify document ownership
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        doc_res = await db.execute(doc_stmt)
        if not doc_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )

        # Check existing junction
        check_stmt = select(collection_documents).where(
            collection_documents.c.collection_id == collection_id,
            collection_documents.c.document_id == document_id,
        )
        check_res = await db.execute(check_stmt)
        if check_res.first():
            return  # Already added

        ins_stmt = insert(collection_documents).values(
            collection_id=collection_id,
            document_id=document_id,
        )
        await db.execute(ins_stmt)
        await db.commit()

    async def remove_document_from_collection(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        collection_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        # Verify collection ownership
        col_stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        col_res = await db.execute(col_stmt)
        if not col_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

        del_stmt = delete(collection_documents).where(
            collection_documents.c.collection_id == collection_id,
            collection_documents.c.document_id == document_id,
        )
        await db.execute(del_stmt)
        await db.commit()



collection_service = CollectionService()
