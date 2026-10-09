import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    """
    Payload for creating an empty conversation thread.
    """
    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional title for the conversation. If omitted, will be auto-generated from the first query.",
    )


class ConversationUpdate(BaseModel):
    """
    Payload for updating conversation metadata.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New title for the conversation.",
    )


class MessageResponse(BaseModel):
    """
    Representation of an individual message within a conversation.
    Includes role, content, and safe metadata such as citations and retrieval provenance.
    Never exposes embedding vectors or server storage paths.
    """
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Safe metadata including citations, sources, latency, and tokens.",
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """
    Summary representation of a conversation thread.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = Field(
        default=None,
        description="Total number of messages in the conversation.",
    )

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    """
    Detailed representation of a conversation thread including its full chronological messages.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = Field(
        default_factory=list,
        description="Chronologically ordered messages in this conversation.",
    )

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    """
    Paginated list of user conversations.
    """
    items: List[ConversationResponse]
    total: int
