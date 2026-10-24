import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# 1. Summary Schemas
class DocumentSummaryRequest(BaseModel):
    mode: str = Field(default="concise", description="'concise' or 'detailed'")
    force_refresh: bool = Field(default=False, description="Bypass cache and regenerate")


class DocumentSummaryResponse(BaseModel):
    document_id: str
    document_filename: str
    mode: str
    summary: str
    key_takeaways: List[str] = []
    cached: bool = False
    generated_at: Optional[str] = None


# 2. Multi-Document Comparison Schemas
class DocumentComparisonRequest(BaseModel):
    document_ids: List[uuid.UUID] = Field(..., min_length=2, max_length=5, description="Document IDs to compare")
    comparison_prompt: Optional[str] = Field(None, max_length=1000, description="Optional custom focus areas")


class DocumentComparisonResponse(BaseModel):
    comparison_id: str
    documents: List[Dict[str, Any]]
    focus_prompt: str
    synthesis: str
    sources: List[Dict[str, Any]]


# 3. Structured Extraction Schemas
class StructuredExtractionRequest(BaseModel):
    target_fields: Optional[List[str]] = Field(None, description="Specific categories to extract")


class StructuredExtractionResponse(BaseModel):
    document_id: str
    document_filename: str
    data: Dict[str, Any]


# 4. Report Schemas
class ReportGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=1000, description="Research or report topic")
    title: Optional[str] = Field(None, max_length=255, description="Report title")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Scope to specific documents")
    collection_id: Optional[uuid.UUID] = Field(None, description="Scope to a collection")


class ReportGenerateResponse(BaseModel):
    report_id: str
    title: str
    topic: str
    generated_at: str
    content_markdown: str
    documents_count: int
    sources: List[Dict[str, Any]]


# 5. Deep Research Schemas
class DeepResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=1000)
    document_id: Optional[uuid.UUID] = None
    max_subquestions: int = Field(default=3, ge=1, le=5)


class DeepResearchResponse(BaseModel):
    research_id: str
    topic: str
    subquestions: List[str]
    steps: List[Dict[str, Any]]
    synthesis: str
    sources: List[Dict[str, Any]]
    has_conflicts: bool


# 6. Knowledge Graph Schemas
class KnowledgeGraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    total_entities: int
    total_relationships: int
