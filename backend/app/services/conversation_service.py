import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message

logger = logging.getLogger("cogniva.services.conversation")


def generate_deterministic_title(query: str, max_length: int = 60) -> str:
    """
    Deterministically generates a concise, readable conversation title from
    the initial user question without calling an external LLM.
    Strips conversational filler prefixes and formats cleanly.
    """
    cleaned = query.strip()
    # Normalize internal whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Remove common introductory filler phrases and leading articles
    pattern = r"^(?:what is|what are|who is|can you tell me about|tell me about|how do i|how does|explain|could you explain)(?:\s+(?:the|our|a|an))?\s+"
    cleaned_prefix = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned_prefix:
        cleaned = cleaned_prefix

    # Strip trailing punctuation
    cleaned = cleaned.rstrip("?.!;,")

    if not cleaned:
        return "New Conversation"

    # Capitalize first character
    cleaned = cleaned[0].upper() + cleaned[1:]

    # Truncate to max_length at word boundary if possible
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > 20:
            cleaned = truncated[:last_space] + "..."
        else:
            cleaned = truncated + "..."

    return cleaned


class ConversationService:
    """
    Manages persistent conversation threads and messages with strict tenant isolation.
    """

    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: Optional[str] = None,
    ) -> Conversation:
        """
        Creates a new conversation thread owned by the authenticated user.
        """
        conv_title = (title or "").strip() or "New Conversation"
        conversation = Conversation(
            user_id=user_id,
            title=conv_title,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    async def list_conversations(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Conversation], int]:
        """
        Retrieves paginated list of conversations owned strictly by user_id,
        ordered by most recently updated first.
        """
        count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        count_res = await db.execute(count_stmt)
        total = count_res.scalar_one()

        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(stmt)
        conversations = list(res.scalars().all())
        return conversations, total

    async def get_conversation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Optional[Conversation]:
        """
        Retrieves a conversation and all its messages in chronological order,
        strictly enforcing tenant ownership.
        """
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        res = await db.execute(stmt)
        conversation = res.scalar_one_or_none()
        if conversation:
            # Ensure messages are ordered chronologically
            conversation.messages.sort(key=lambda m: m.created_at)
        return conversation

    async def get_conversation_recent_messages(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int = 6,
    ) -> List[Message]:
        """
        Retrieves the N most recent messages for bounded conversation context,
        returning them in chronological order.
        Verifies that conversation belongs to user_id.
        """
        # First verify conversation ownership
        ownership_stmt = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        res = await db.execute(ownership_stmt)
        if not res.scalar_one_or_none():
            return []

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        msg_res = await db.execute(stmt)
        recent_desc = list(msg_res.scalars().all())
        # Return in ascending chronological order
        return list(reversed(recent_desc))

    async def delete_conversation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        """
        Deletes a conversation and cascades to all associated messages.
        Returns False if conversation does not exist or belongs to another user.
        """
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        res = await db.execute(stmt)
        conversation = res.scalar_one_or_none()
        if not conversation:
            return False

        await db.delete(conversation)
        await db.commit()
        return True

    async def persist_turn(
        self,
        db: AsyncSession,
        conversation: Conversation,
        user_query: str,
        assistant_answer: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Message, Message]:
        """
        Atomically records a complete user question and assistant answer turn,
        attaching validated citation and retrieval metadata.
        Updates conversation updated_at timestamp.
        """
        # User message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=user_query,
            metadata_={},
        )
        db.add(user_msg)

        # Assistant message with safe provenance & citation metadata
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_answer,
            metadata_=metadata or {},
        )
        db.add(assistant_msg)

        # Update title if it is currently default "New Conversation"
        if conversation.title == "New Conversation":
            conversation.title = generate_deterministic_title(user_query)

        # Update timestamp
        conversation.updated_at = func.now()

        await db.commit()
        await db.refresh(user_msg)
        await db.refresh(assistant_msg)
        await db.refresh(conversation)

        return user_msg, assistant_msg


# Singleton instance
conversation_service = ConversationService()
