import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.llm import llm_service, LLMMessage
from app.services.rag.citations import citation_validator

logger = logging.getLogger("cogniva.summary_service")


class SummaryService:
    """
    Synthesizes concise or comprehensive document summaries grounded in authentic chunks.
    Preserves source citations and caches results in document metadata with timestamped invalidation.
    """

    async def get_document_summary(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        mode: str = "concise",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        res = await db.execute(stmt)
        document = res.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )

        if document.status != "processed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot summarize document with status '{document.status}'. Document must be processed first.",
            )

        cache_key = f"summary_{mode}"
        meta = dict(document.metadata_ or {})

        # Check existing cached summary if not forcing refresh
        if not force_refresh and cache_key in meta:
            cached = meta[cache_key]
            if isinstance(cached, dict) and "summary" in cached:
                return {
                    "document_id": str(document.id),
                    "document_filename": document.original_filename or document.filename,
                    "mode": mode,
                    "summary": cached.get("summary", ""),
                    "key_takeaways": cached.get("key_takeaways", []),
                    "cached": True,
                    "generated_at": cached.get("generated_at"),
                }

        # Retrieve first N chunks of the document for representative context
        chunk_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(10)
        )
        chunk_res = await db.execute(chunk_stmt)
        chunks = chunk_res.scalars().all()

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chunks found for this document.",
            )

        # Assemble context with source identifiers
        context_blocks = []
        for idx, chunk in enumerate(chunks):
            cid = f"S{idx + 1}"
            page_info = f"p.{chunk.page_number}" if chunk.page_number else f"chunk {chunk.chunk_index}"
            context_blocks.append(f"[{cid}] ({document.original_filename or document.filename}, {page_info}):\n{chunk.content}")

        context_text = "\n\n".join(context_blocks)

        prompt = (
            f"You are an enterprise knowledge intelligence agent. Synthesize a {mode.upper()} summary of the document below.\n\n"
            f"GUIDELINES:\n"
            f"1. Rely exclusively on the provided context.\n"
            f"2. Cite supporting facts with bracketed tags like [S1], [S2] where applicable.\n"
            f"3. Format your response into two distinct sections:\n"
            f"   - SUMMARY: A {mode} narrative overview of the document's core purpose and content.\n"
            f"   - KEY_TAKEAWAYS: 3 to 5 bullet points starting with '- ' summarizing critical data points, metrics, obligations, or findings.\n\n"
            f"DOCUMENT CONTEXT:\n{context_text}"
        )

        messages = [
            LLMMessage(role="system", content="You are a strict enterprise document summarizer. Never speculate or hallucinate outside the text."),
            LLMMessage(role="user", content=prompt),
        ]

        llm_resp = await llm_service.generate(messages=messages, temperature=0.1)
        raw_text = llm_resp.content

        # Parse sections
        summary_text = raw_text
        takeaways: List[str] = []

        if "KEY_TAKEAWAYS:" in raw_text:
            parts = raw_text.split("KEY_TAKEAWAYS:")
            summary_part = parts[0].replace("SUMMARY:", "").strip()
            takeaways_part = parts[1].strip()
            summary_text = summary_part
            takeaways = [
                line.lstrip("- ").strip()
                for line in takeaways_part.split("\n")
                if line.strip() and (line.strip().startswith("-") or line.strip().startswith("•"))
            ]
        elif "SUMMARY:" in raw_text:
            summary_text = raw_text.replace("SUMMARY:", "").strip()

        now_iso = datetime.now(timezone.utc).isoformat()
        summary_payload = {
            "summary": summary_text,
            "key_takeaways": takeaways,
            "generated_at": now_iso,
        }

        # Cache in document metadata
        meta[cache_key] = summary_payload
        document.metadata_ = meta
        await db.commit()

        return {
            "document_id": str(document.id),
            "document_filename": document.original_filename or document.filename,
            "mode": mode,
            "summary": summary_text,
            "key_takeaways": takeaways,
            "cached": False,
            "generated_at": now_iso,
        }


summary_service = SummaryService()
