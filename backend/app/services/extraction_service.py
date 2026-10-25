import csv
import io
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.llm import llm_service, LLMMessage

logger = logging.getLogger("cogniva.extraction_service")


class ExtractionService:
    """
    Extracts structured enterprise fields (entities, dates, metrics, obligations, risks, action items)
    with exact source provenance. Enables structured export to JSON and CSV.
    """

    async def extract_structured_data(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        target_fields: Optional[List[str]] = None,
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

        chunk_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(100)
        )
        c_res = await db.execute(chunk_stmt)
        chunks = c_res.scalars().all()

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chunks found for this document.",
            )

        context_blocks = []
        for c in chunks:
            p_str = f"Page {c.page_number}" if c.page_number else f"Unit {c.chunk_index}"
            context_blocks.append(f"[{p_str}]:\n{c.content}")

        context_text = "\n\n".join(context_blocks)

        fields_desc = target_fields or ["entities", "dates", "metrics", "obligations", "risks", "action_items"]

        prompt = (
            f"You are a structured enterprise data extraction engine. Extract structured intelligence from the document text below.\n\n"
            f"TARGET CATEGORIES: {', '.join(fields_desc)}\n\n"
            f"STRICT EXTRACTION RULES:\n"
            f"1. ENTITIES: Extract meaningful, complete proper names (e.g., 'ElderShield AI', not overlapping fragments like 'ElderShield AI proposes an AI'). "
            f"Explicitly extract named technologies with accurate classification (e.g., Python as PROGRAMMING_LANGUAGE, FastAPI as FRAMEWORK/BACKEND, React as FRAMEWORK/FRONTEND, "
            f"NLP as TECHNOLOGY, Machine learning models as TECHNOLOGY, URL parsing/security checks as SECURITY_COMPONENT). "
            f"NEVER classify generic headings (like 'Problem Statement', 'System Architecture', 'Evaluation Criteria') as technologies or products. Include source context sentence.\n"
            f"2. RISKS: Distinguish actual threats, attack vectors, vulnerabilities, and consequences (e.g., phishing links, fraudulent messages, impersonation attempts, scam calls, "
            f"financial losses, identity theft, privacy breaches) from general problem statements or accessibility goals. "
            f"Do not invent severity levels if the source does not assign them; leave severity null or unassigned.\n"
            f"3. ACTION ITEMS: Extract concrete actionable recommendations and protective guidance (e.g., independently verifying the sender, avoiding unknown links, "
            f"never sharing confidential credentials). Do not invent task assignees or deadlines.\n"
            f"4. METRICS & EVALUATION: Extract precision, recall, and false-positive rates as evaluation metrics. Extract usability testing as an evaluation method. "
            f"Retain representative legitimate and suspicious examples as evaluation material/dataset, without misclassifying them as metrics.\n"
            f"5. DATES & OBLIGATIONS: Return empty arrays [] if the document contains no supported dates or contractual obligations. Never fabricate dates, parties, or deadlines.\n"
            f"6. PROVENANCE: Associate each item with its correct source page or unit number.\n\n"
            f"OUTPUT FORMAT: Return a valid JSON object matching this structure EXACTLY (do not wrap in markdown quotes if possible, output pure JSON):\n"
            f"{{\n"
            f'  "entities": [{{"name": "...", "type": "ORGANIZATION|PERSON|PRODUCT|TECHNOLOGY|FRAMEWORK|DATABASE|SECURITY_COMPONENT", "page": 1, "context": "..."}}],\n'
            f'  "dates": [{{"date": "...", "event": "...", "page": 1}}],\n'
            f'  "metrics": [{{"metric": "...", "value": "...", "unit": "...", "page": 1}}],\n'
            f'  "obligations": [{{"party": "...", "obligation": "...", "deadline": "...", "page": 1}}],\n'
            f'  "risks": [{{"risk": "...", "severity": "HIGH|MEDIUM|LOW|Unassigned", "page": 1}}],\n'
            f'  "action_items": [{{"item": "...", "assignee": "...", "page": 1}}]\n'
            f"}}\n\n"
            f"DOCUMENT PASSAGES:\n{context_text}"
        )

        messages = [
            LLMMessage(role="system", content="You are a strict JSON data extractor. Output ONLY valid JSON."),
            LLMMessage(role="user", content=prompt),
        ]

        llm_resp = await llm_service.generate(messages=messages, temperature=0.0)
        raw_json = llm_resp.content.strip()

        # Clean markdown fence if present
        if raw_json.startswith("```"):
            raw_json = raw_json.split("\n", 1)[1]
            if raw_json.endswith("```"):
                raw_json = raw_json.rsplit("```", 1)[0]
            raw_json = raw_json.strip()

        try:
            extracted_json = json.loads(raw_json)
        except Exception:
            # Fallback structure if JSON parse failed
            extracted_json = {
                "entities": [],
                "dates": [],
                "metrics": [],
                "obligations": [],
                "risks": [],
                "action_items": [],
                "raw_text": raw_json,
            }

        return {
            "document_id": str(document.id),
            "document_filename": document.original_filename or document.filename,
            "data": extracted_json,
        }

    def export_as_csv(self, extracted_data: Dict[str, Any]) -> str:
        """
        Converts extracted structured items into a tabular CSV string.
        Robust to both object dictionaries and string values.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Category", "Item / Name", "Detail / Value", "Context / Entity Type", "Page"])

        data = extracted_data.get("data", {})
        
        # Entities
        for ent in data.get("entities", []) or data.get("key_entities", []):
            if isinstance(ent, dict):
                writer.writerow(["Entity", ent.get("name", ""), ent.get("type", ""), ent.get("context", ""), ent.get("page", "")])
            else:
                writer.writerow(["Entity", str(ent), "", "", ""])

        # Dates
        for dt in data.get("dates", []):
            if isinstance(dt, dict):
                writer.writerow(["Date", dt.get("date", ""), dt.get("event", ""), "", dt.get("page", "")])
            else:
                writer.writerow(["Date", str(dt), "", "", ""])

        # Metrics
        for met in data.get("metrics", []):
            if isinstance(met, dict):
                writer.writerow(["Metric", met.get("metric", ""), met.get("value", ""), met.get("unit", ""), met.get("page", "")])
            else:
                writer.writerow(["Metric", str(met), "", "", ""])

        # Obligations
        for ob in data.get("obligations", []):
            if isinstance(ob, dict):
                writer.writerow(["Obligation", ob.get("party", ""), ob.get("obligation", ""), ob.get("deadline", ""), ob.get("page", "")])
            else:
                writer.writerow(["Obligation", str(ob), "", "", ""])

        # Risks
        for rk in data.get("risks", []):
            if isinstance(rk, dict):
                r_name = rk.get("risk") or rk.get("name") or rk.get("item") or ""
                r_sev = rk.get("severity") or "Unassigned"
                writer.writerow(["Risk", r_name, r_sev, rk.get("context", ""), rk.get("page", "")])
            else:
                writer.writerow(["Risk", str(rk), "Unassigned", "", ""])

        # Action Items
        for ai in data.get("action_items", []):
            if isinstance(ai, dict):
                a_name = ai.get("item") or ai.get("name") or ""
                a_who = ai.get("assignee") or "Unassigned"
                writer.writerow(["Action Item", a_name, a_who, ai.get("context", ""), ai.get("page", "")])
            else:
                writer.writerow(["Action Item", str(ai), "Unassigned", "", ""])

        return output.getvalue()


extraction_service = ExtractionService()
