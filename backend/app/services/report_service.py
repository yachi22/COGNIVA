import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.collection import Collection
from app.services.llm import llm_service, LLMMessage

logger = logging.getLogger("cogniva.report_service")


class ReportService:
    """
    Synthesizes comprehensive, evidence-backed enterprise research reports.
    Formats findings with verifiable citations and supports Markdown/HTML exports.
    """

    async def generate_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        topic: str,
        title: Optional[str] = None,
        document_ids: Optional[List[uuid.UUID]] = None,
        collection_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        clean_topic = topic.strip()
        if not clean_topic:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Research topic cannot be empty.",
            )

        target_docs: List[Document] = []

        # 1. Resolve documents from collection if specified
        if collection_id:
            col_stmt = (
                select(Collection)
                .where(
                    Collection.id == collection_id,
                    Collection.user_id == user_id,
                )
                .options(selectinload(Collection.documents))
            )
            col_res = await db.execute(col_stmt)
            col = col_res.scalar_one_or_none()
            if not col:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Collection not found or access denied.",
                )
            target_docs = list(col.documents)

        # 2. Or resolve from explicit document_ids
        elif document_ids:
            doc_stmt = select(Document).where(
                Document.id.in_(document_ids),
                Document.user_id == user_id,
            )
            doc_res = await db.execute(doc_stmt)
            target_docs = doc_res.scalars().all()
            if not target_docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Specified documents not found or access denied.",
                )

        # 3. Or default to all user's processed documents
        else:
            all_stmt = (
                select(Document)
                .where(
                    Document.user_id == user_id,
                    Document.status == "processed",
                )
                .limit(10)
            )
            all_res = await db.execute(all_stmt)
            target_docs = all_res.scalars().all()

        if not target_docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No available processed documents found to generate report.",
            )

        # 4. Gather representative chunks
        evidence_blocks: List[str] = []
        source_manifest: List[Dict[str, Any]] = []
        source_counter = 1

        for doc in target_docs:
            chunk_stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
                .limit(5)
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
                    "filename": doc_name,
                    "document_filename": doc_name,
                    "page_number": c.page_number,
                    "chunk_id": str(c.id),
                    "excerpt": c.content[:240] + ("..." if len(c.content) > 240 else ""),
                })

        context_text = "\n\n".join(evidence_blocks)
        report_title = title.strip() if title else f"Intelligence Report: {clean_topic[:60]}"

        prompt = (
            f"You are an enterprise research intelligence officer. Generate a comprehensive, professional intelligence report titled '{report_title}' addressing the topic: '{clean_topic}'.\n\n"
            f"STRUCTURE REQUIREMENTS:\n"
            f"# {report_title}\n\n"
            f"## 1. Executive Summary\n"
            f"Brief high-level overview of core conclusions and strategic takeaways.\n\n"
            f"## 2. Analyzed Corpus & Scope\n"
            f"Summary of knowledge sources reviewed and scope boundary.\n\n"
            f"## 3. Detailed Evidence & Key Findings\n"
            f"In-depth analysis structured by sub-theme. Every statement must cite source tags (e.g. [S1], [S2]).\n\n"
            f"## 4. Risks & Operational Considerations\n"
            f"Highlight compliance, financial, technical, or legal risks identified.\n\n"
            f"## 5. Strategic Recommendations\n"
            f"Actionable recommendations based on the findings.\n\n"
            f"EVIDENCE CONTEXT:\n{context_text}"
        )

        messages = [
            LLMMessage(role="system", content="You are an enterprise report analyst. Produce rigorous, grounded reports citing evidence tags accurately."),
            LLMMessage(role="user", content=prompt),
        ]

        llm_resp = await llm_service.generate(messages=messages, temperature=0.1)

        return {
            "report_id": str(uuid.uuid4()),
            "title": report_title,
            "topic": clean_topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "content_markdown": llm_resp.content,
            "documents_count": len(target_docs),
            "sources": source_manifest,
        }


report_service = ReportService()
