import logging
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.rag import RAGQueryResponse, RAGSourceItem
from app.services.retrieval_service import retrieval_service
from app.services.rag.context import context_assembler, ContextAssembler
from app.services.rag.citations import citation_validator, CitationValidator
from app.services.conversation_service import conversation_service, ConversationService
from app.services.llm import (
    llm_service,
    LLMService,
    build_rag_messages,
    INSUFFICIENT_EVIDENCE_RESPONSE,
    MissingLLMConfigurationError,
    LLMError,
)

logger = logging.getLogger("cogniva.rag.service")


class RAGService:
    """
    Core Retrieval-Augmented Generation (RAG) orchestration service.
    Coordinates semantic vector retrieval, structured context assembly,
    prompt injection defense, LLM answer generation, backend citation validation,
    and persistent conversation turn history.
    """

    def __init__(
        self,
        assembler: Optional[ContextAssembler] = None,
        llm: Optional[LLMService] = None,
        validator: Optional[CitationValidator] = None,
        conv_service: Optional[ConversationService] = None,
    ):
        self.context_assembler = assembler or context_assembler
        self.llm_service = llm or llm_service
        self.citation_validator = validator or citation_validator
        self.conversation_service = conv_service or conversation_service

    async def answer_query(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_id: Optional[uuid.UUID] = None,
        min_similarity: Optional[float] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> RAGQueryResponse:
        """
        Executes end-to-end RAG pipeline with persistent conversation history:
        1. Validates query and verifies/creates conversation thread with tenant isolation.
        2. Retrieves bounded recent conversation history for follow-up context.
        3. Executes tenant-isolated semantic retrieval over pgvector (with follow-up fallback).
        4. Early exit with deterministic response if no relevant chunks are found.
        5. Assembles structured evidence context respecting token/character budgets.
        6. Constructs grounded prompt with injection defense boundaries and conversation history.
        7. Calls LLM provider to synthesize answer.
        8. Validates citations referenced by LLM against authentic retrieved chunks.
        9. Persists user query and assistant answer with full provenance/citation metadata.
        """
        clean_query = query.strip()
        if not clean_query:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Query text cannot be empty.",
            )

        # 1. Resolve or create conversation with strict tenant verification
        if conversation_id is not None:
            conversation = await self.conversation_service.get_conversation(
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied.",
                )
        else:
            conversation = await self.conversation_service.create_conversation(
                db=db,
                user_id=user_id,
                title="New Conversation",
            )

        # 2. Retrieve bounded recent conversation history (max 6 messages / 3 turns)
        recent_msgs = await self.conversation_service.get_conversation_recent_messages(
            db=db,
            user_id=user_id,
            conversation_id=conversation.id,
            limit=6,
        )
        history = [{"role": m.role, "content": m.content} for m in recent_msgs]

        # 3. Semantic retrieval from PostgreSQL pgvector
        retrieval_res = await retrieval_service.search(
            db=db,
            user_id=user_id,
            query=clean_query,
            top_k=top_k,
            document_id=document_id,
            min_similarity=min_similarity,
        )

        # If zero results and recent history exists, try follow-up query enrichment
        if (retrieval_res.total == 0 or not retrieval_res.results) and recent_msgs:
            last_user_q = next((m.content for m in reversed(recent_msgs) if m.role == "user"), None)
            if last_user_q and last_user_q.strip() != clean_query:
                followup_search = f"{last_user_q} {clean_query}"
                retrieval_res = await retrieval_service.search(
                    db=db,
                    user_id=user_id,
                    query=followup_search,
                    top_k=top_k,
                    document_id=document_id,
                    min_similarity=min_similarity,
                )

        # 4. Early exit on empty or below-threshold retrieval
        if retrieval_res.total == 0 or not retrieval_res.results:
            user_msg, assistant_msg = await self.conversation_service.persist_turn(
                db=db,
                conversation=conversation,
                user_query=clean_query,
                assistant_answer=INSUFFICIENT_EVIDENCE_RESPONSE,
                metadata={
                    "retrieval_count": 0,
                    "sources": [],
                    "citations": [],
                    "insufficient_evidence": True,
                },
            )
            return RAGQueryResponse(
                query=clean_query,
                answer=INSUFFICIENT_EVIDENCE_RESPONSE,
                retrieval_count=0,
                sources=[],
                citations=[],
                insufficient_evidence=True,
                conversation_id=conversation.id,
                user_message_id=user_msg.id,
                assistant_message_id=assistant_msg.id,
            )

        # 5. Assemble structured context respecting token/character limits
        context_text, included_items = self.context_assembler.assemble(retrieval_res.results)

        if not included_items:
            user_msg, assistant_msg = await self.conversation_service.persist_turn(
                db=db,
                conversation=conversation,
                user_query=clean_query,
                assistant_answer=INSUFFICIENT_EVIDENCE_RESPONSE,
                metadata={
                    "retrieval_count": 0,
                    "sources": [],
                    "citations": [],
                    "insufficient_evidence": True,
                },
            )
            return RAGQueryResponse(
                query=clean_query,
                answer=INSUFFICIENT_EVIDENCE_RESPONSE,
                retrieval_count=0,
                sources=[],
                citations=[],
                insufficient_evidence=True,
                conversation_id=conversation.id,
                user_message_id=user_msg.id,
                assistant_message_id=assistant_msg.id,
            )

        # 6. Construct prompt with prompt injection defense boundary & history
        messages = build_rag_messages(
            query=clean_query,
            context_text=context_text,
            history=history,
        )

        # 7. Call LLM provider (exceptions bubble up without saving fake answers)
        try:
            llm_res = await self.llm_service.generate(messages)
            answer = llm_res.content.strip()
        except MissingLLMConfigurationError as e:
            logger.error(f"LLM configuration missing: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )
        except LLMError as e:
            logger.error(f"LLM generation failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"RAG answer generation failed: {str(e)}",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during RAG answer generation: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error during RAG answer generation.",
            )

        # Determine if response indicated insufficient evidence
        is_insufficient = (
            INSUFFICIENT_EVIDENCE_RESPONSE.lower() in answer.lower()
            or "do not contain enough information" in answer.lower()
        )

        sources = [
            RAGSourceItem(
                citation_id=f"S{idx}",
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                chunk_index=item.chunk_index,
                document_filename=item.document_original_filename or item.document_filename,
                page_number=item.page_number,
                similarity_score=item.similarity_score,
                cosine_distance=item.cosine_distance,
                metadata=item.metadata,
            )
            for idx, item in enumerate(included_items, start=1)
        ]

        # 8. Validate citations referenced by the LLM against retrieved sources
        citations = self.citation_validator.extract_and_validate(
            answer=answer,
            sources=included_items,
        )

        # 9. Persist conversation turn with structured provenance & citations
        sources_payload = [s.model_dump(mode="json") for s in sources]
        citations_payload = [c.model_dump(mode="json") for c in citations]

        user_msg, assistant_msg = await self.conversation_service.persist_turn(
            db=db,
            conversation=conversation,
            user_query=clean_query,
            assistant_answer=answer,
            metadata={
                "retrieval_count": len(sources),
                "sources": sources_payload,
                "citations": citations_payload,
                "insufficient_evidence": is_insufficient,
            },
        )

        return RAGQueryResponse(
            query=clean_query,
            answer=answer,
            retrieval_count=len(sources),
            sources=sources,
            citations=citations,
            insufficient_evidence=is_insufficient,
            conversation_id=conversation.id,
            user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id,
        )


# Singleton instance
rag_service = RAGService()
