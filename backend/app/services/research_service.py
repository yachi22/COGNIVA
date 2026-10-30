import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.retrieval_service import retrieval_service
from app.services.llm import llm_service, LLMMessage

logger = logging.getLogger("cogniva.research_service")


class ResearchService:
    """
    Coordinates evidence-grounded multi-step research workflows.
    Decomposes questions into explicit subquestions, conducts iterative targeted retrieval passes,
    and synthesizes findings into a cited dossier with conflict detection.
    """

    async def execute_deep_research(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        topic: str,
        document_id: Optional[uuid.UUID] = None,
        max_subquestions: int = 3,
    ) -> Dict[str, Any]:
        clean_topic = topic.strip()
        if not clean_topic:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Research prompt cannot be empty.",
            )

        # 0. Upfront tenant authorization check for scoped document
        if document_id is not None:
            doc_stmt = select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            doc_res = await db.execute(doc_stmt)
            if not doc_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found or access denied.",
                )

        # 1. Step 1: Decompose problem into explicit subquestions using LLM
        decomp_prompt = (
            f"You are an enterprise research orchestrator. Decompose the following strategic inquiry into 2 to {max_subquestions} focused, factual subquestions.\n\n"
            f"INQUIRY: {clean_topic}\n\n"
            f"OUTPUT FORMAT: Return a valid JSON array of strings, for example: [\"Subquestion 1?\", \"Subquestion 2?\"]\n"
            f"Do not include explanation, return ONLY the JSON array."
        )

        decomp_resp = await llm_service.generate(
            messages=[
                LLMMessage(role="system", content="You are a research decomposition planner. Output only valid JSON arrays."),
                LLMMessage(role="user", content=decomp_prompt),
            ],
            temperature=0.0,
        )

        subquestions: List[str] = []
        try:
            raw_json = decomp_resp.content.strip()
            if raw_json.startswith("```"):
                raw_json = raw_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                subquestions = [str(q).strip() for q in parsed if str(q).strip()][:max_subquestions]
        except Exception:
            subquestions = [clean_topic]

        if not subquestions:
            subquestions = [clean_topic]

        # 2. Step 2: Conduct scoped retrieval passes for each subquestion
        steps_log: List[Dict[str, Any]] = []
        all_sources: List[Dict[str, Any]] = []
        assembled_evidence_blocks: List[str] = []
        seen_chunk_ids = set()
        source_counter = 1

        for sq in subquestions:
            retrieval_res = await retrieval_service.search(
                db=db,
                user_id=user_id,
                query=sq,
                top_k=3,
                document_id=document_id,
                hybrid=True,
            )

            sq_sources = []
            for item in retrieval_res.results:
                if item.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(item.chunk_id)
                    cid = f"S{source_counter}"
                    source_counter += 1
                    page_info = f"p.{item.page_number}" if item.page_number is not None else f"chunk {item.chunk_index}"
                    assembled_evidence_blocks.append(
                        f"[{cid}] Document '{item.document_filename}' ({page_info}):\n{item.content}"
                    )
                    source_dict = {
                        "citation_id": cid,
                        "document_id": str(item.document_id),
                        "document_filename": item.document_filename,
                        "page_number": item.page_number,
                        "chunk_id": str(item.chunk_id),
                        "similarity_score": item.similarity_score,
                    }
                    all_sources.append(source_dict)
                    sq_sources.append(source_dict)

            steps_log.append({
                "subquestion": sq,
                "retrieved_count": len(sq_sources),
                "sources": sq_sources,
            })

        # 3. Step 3: Evidence check
        has_sufficient_evidence = len(assembled_evidence_blocks) > 0
        if not has_sufficient_evidence:
            return {
                "research_id": str(uuid.uuid4()),
                "topic": clean_topic,
                "subquestions": subquestions,
                "steps": steps_log,
                "synthesis": "Insufficient evidence found in the document repository to answer this inquiry.",
                "sources": [],
                "has_conflicts": False,
            }

        context_text = "\n\n".join(assembled_evidence_blocks)

        # 4. Step 4: Synthesize unified research dossier
        synthesis_prompt = (
            f"You are an enterprise research intelligence officer. Synthesize a comprehensive research dossier for: '{clean_topic}'.\n\n"
            f"SUBQUESTIONS EXPLORED:\n"
            + "\n".join(f"- {sq}" for sq in subquestions)
            + "\n\n"
            f"GUIDELINES:\n"
            f"1. Rely exclusively on the retrieved evidence below.\n"
            f"2. Cite every claim with tags like [S1], [S2].\n"
            f"3. Note any conflicting sources or contradictory statements between documents.\n"
            f"4. Clearly identify any subquestion where evidence is insufficient or missing.\n"
            f"5. Structure output with sections: Executive Summary, Subquestion Findings, Conflicting Evidence (if any), and Concluding Assessment.\n\n"
            f"RETRIEVED EVIDENCE:\n{context_text}"
        )

        synth_resp = await llm_service.generate(
            messages=[
                LLMMessage(role="system", content="You are a strict multi-step research analyst. Base findings exclusively on evidence."),
                LLMMessage(role="user", content=synthesis_prompt),
            ],
            temperature=0.1,
        )

        return {
            "research_id": str(uuid.uuid4()),
            "topic": clean_topic,
            "subquestions": subquestions,
            "steps": steps_log,
            "synthesis": synth_resp.content,
            "sources": all_sources,
            "has_conflicts": "conflict" in synth_resp.content.lower() or "contradict" in synth_resp.content.lower(),
        }


research_service = ResearchService()
