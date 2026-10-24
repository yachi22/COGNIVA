import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionDetailResponse,
    CollectionListResponse,
    AddDocumentToCollectionRequest,
)
from app.services.collection_service import collection_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = await collection_service.create_collection(
        db=db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        color=data.color,
    )
    await audit_service.log_event(
        db=db,
        action="COLLECTION_CREATE",
        resource_type="collection",
        user_id=current_user.id,
        resource_id=str(col.id),
        details={"name": col.name},
    )
    return CollectionResponse(
        id=str(col.id),
        user_id=str(col.user_id),
        name=col.name,
        description=col.description,
        color=col.color,
        document_count=0,
        documents_count=0,
        created_at=col.created_at.isoformat() if col.created_at else None,
        updated_at=col.updated_at.isoformat() if col.updated_at else None,
    )


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cols = await collection_service.list_collections(db=db, user_id=current_user.id)
    items = [CollectionResponse(**c) for c in cols]
    return CollectionListResponse(items=items, total=len(items))


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid.UUID,
    data: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    col = await collection_service.update_collection(
        db=db,
        user_id=current_user.id,
        collection_id=collection_id,
        name=data.name,
        description=data.description,
        color=data.color,
    )
    return CollectionResponse(
        id=str(col.id),
        user_id=str(col.user_id),
        name=col.name,
        description=col.description,
        color=col.color,
        document_count=0,
        documents_count=0,
        created_at=col.created_at.isoformat() if col.created_at else None,
        updated_at=col.updated_at.isoformat() if col.updated_at else None,
    )


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection_detail(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await collection_service.get_collection_detail(
        db=db,
        user_id=current_user.id,
        collection_id=collection_id,
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await collection_service.delete_collection(
        db=db,
        user_id=current_user.id,
        collection_id=collection_id,
    )
    await audit_service.log_event(
        db=db,
        action="COLLECTION_DELETE",
        resource_type="collection",
        user_id=current_user.id,
        resource_id=str(collection_id),
    )


@router.post("/{collection_id}/documents", status_code=status.HTTP_200_OK)
async def add_document_to_collection(
    collection_id: uuid.UUID,
    data: AddDocumentToCollectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await collection_service.add_document_to_collection(
        db=db,
        user_id=current_user.id,
        collection_id=collection_id,
        document_id=data.document_id,
    )
    return {"message": "Document added to collection successfully."}


@router.delete("/{collection_id}/documents/{document_id}", status_code=status.HTTP_200_OK)
async def remove_document_from_collection(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await collection_service.remove_document_from_collection(
        db=db,
        user_id=current_user.id,
        collection_id=collection_id,
        document_id=document_id,
    )
    return {"message": "Document removed from collection successfully."}
