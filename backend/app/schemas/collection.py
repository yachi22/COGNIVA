import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Collection name.")
    description: Optional[str] = Field(None, max_length=1000, description="Collection description.")
    color: str = Field(default="#267653", max_length=50, description="Hex color identifier.")


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Collection name.")
    description: Optional[str] = Field(None, max_length=1000, description="Collection description.")
    color: Optional[str] = Field(None, max_length=50, description="Hex color identifier.")


class CollectionDocumentItem(BaseModel):
    id: str
    filename: str
    original_filename: Optional[str] = None
    file_type: str
    status: str
    created_at: Optional[str] = None


class CollectionResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    color: str
    document_count: int = 0
    documents_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CollectionDetailResponse(CollectionResponse):
    documents: List[CollectionDocumentItem] = []


class CollectionListResponse(BaseModel):
    items: List[CollectionResponse] = []
    total: int = 0


class AddDocumentToCollectionRequest(BaseModel):
    document_id: uuid.UUID
