import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.llm import llm_service, LLMMessage

logger = logging.getLogger("cogniva.comparison_service")


class ComparisonService:
    """
    Compares 2+ authorized enterprise documents.
    Synthesizes common themes, material differences, contradictory figures,
    and missing clauses with verified provenance citations.
    """

    async def compare_documents(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_ids: List[uuid.UUID],
        comparison_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        if len(document_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 documents are required for multi-document comparison.",
            )

        if len(document_ids) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A maximum of 5 documents can be compared simultaneously.",
            )

        # 1. Fetch and verify tenant authorization for all documents
        stmt = select(Document).where(
            Document.id.in_(document_ids),
            Document.user_id == user_id,
        )
        res = await db.execute(stmt)
        docs = res.scalars().all()

        found_ids = {d.id for d in docs}
        missing_ids = set(document_ids) - found_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"One or more documents not found or access denied: {[str(m) for m in missing_ids]}",
            )

        # 2. Gather top chunks from each document
        evidence_blocks: List[str] = []
        source_manifest: List[Dict[str, Any]] = []
        source_counter = 1

        for doc in docs:
            chunk_stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
                .limit(6)
            )
            c_res = await db.execute(chunk_stmt)
            chunks = c_res.scalars().all()

            doc_name = doc.original_filename or doc.filename
            for c in chunks:
                cid = f"S{source_counter}"
                source_counter += 1
                page_info = f"p.{c.page_number}" if c.page_number is not None else f"chunk {c.chunk_index}"
                evidence_blocks.append(f"[{cid}] Document '{doc_name}' ({page_info}):\n{c.content}")
                source_manifest.append({
                    "citation_id": cid,
                    "document_id": str(doc.id),
                    "document_filename": doc_name,
                    "page_number": c.page_number,
                    "chunk_id": str(c.id),
                })

        context_text = "\n\n".join(evidence_blocks)

        focus = comparison_prompt.strip() if comparison_prompt else "common themes, material differences, and contradictory figures or terms"

        prompt = (
            f"You are an enterprise knowledge comparison analyst. Perform an evidence-backed comparative analysis of the documents below focusing on: {focus}.\n\n"
            f"STRICT OPERATING RULES:\n"
            f"1. Base findings exclusively on the provided document excerpts.\n"
            f"2. Every material statement must include citation tags (e.g. [S1], [S2]).\n"
            f"3. Explicitly distinguish contradictory statements (e.g. Doc A states X while Doc B states Y) from missing information (e.g. Doc A specifies X, whereas Doc B is silent).\n"
            f"4. Format your output into clear markdown sections:\n"
            f"   ### Executive Summary\n"
            f"   ### Common Alignments & Shared Terms\n"
            f"   ### Material Differences & Discrepancies\n"
            f"   ### Contradictions & Conflicting Statements\n"
            f"   ### Omissions & Gaps (Silent clauses)\n\n"
            f"DOCUMENT PASSAGES:\n{context_text}"
        )

        messages = [
            LLMMessage(role="system", content="You are a strict enterprise comparison engine. Synthesize precise differences with citations. Never speculate."),
            LLMMessage(role="user", content=prompt),
        ]

        llm_resp = await llm_service.generate(messages=messages, temperature=0.1)

        return {
            "comparison_id": str(uuid.uuid4()),
            "documents": [
                {
                    "id": str(d.id),
                    "filename": d.original_filename or d.filename,
                    "file_type": d.file_type,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in docs
            ],
            "focus_prompt": focus,
            "synthesis": llm_resp.content,
            "sources": source_manifest,
        }


comparison_service = ComparisonService()
