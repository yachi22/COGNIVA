import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_type: str
    status: str


class DocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    original_filename: str
    file_type: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentResponse]


class DocumentDeleteResponse(BaseModel):
    message: str
    id: uuid.UUID


class ExtractedUnitResponse(BaseModel):
    unit_type: str
    page_number: Optional[int] = None
    sequence_number: int
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedDocumentResponse(BaseModel):
    document_id: uuid.UUID
    file_type: str
    total_pages: Optional[int] = None
    total_units: int
    total_characters: int
    total_words: int
    units: List[ExtractedUnitResponse]
    extracted_at: datetime


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentChunkListResponse(BaseModel):
    total: int
    document_id: uuid.UUID
    chunks: List[DocumentChunkResponse]


class DocumentChunkDetailResponse(BaseModel):
    """
    Detailed chunk view for secure citation and provenance inspection.
    Excludes embeddings, filesystem storage paths, and secrets.
    """
    id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

