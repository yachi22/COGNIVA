import re
from typing import Dict, List, Set, Tuple
from app.schemas.citation import CitationItem
from app.schemas.retrieval import RetrievalResultItem

# Matches citation tags like [S1], [S2], [S12], etc.
CITATION_TAG_PATTERN = re.compile(r"\[(S\d+)\]")


class CitationValidator:
    """
    Validates LLM-generated citation references against authentic backend-retrieved chunks.
    
    CORE SECURITY PRINCIPLE: THE BACKEND OWNS CITATIONS.
    - Never trusts the LLM to invent, format, or determine which sources exist.
    - Generates response-scoped citation IDs (S1, S2, ...) mapped to retrieval rank.
    - Rejects or ignores unknown citation IDs (e.g., S99, S12).
    - Prevents model from creating new sources or pointing to unretrieved chunks.
    - Never trusts document UUIDs or database IDs produced by an LLM.
    - Preserves deterministic source ordering.
    - Never fabricates citations if the model generated none.
    """

    @staticmethod
    def extract_and_validate(
        answer: str,
        sources: List[RetrievalResultItem],
    ) -> List[CitationItem]:
        """
        Extracts [S#] citations from LLM answer, validates each against retrieved sources,
        and returns structured CitationItem objects for all valid citations.
        """
        if not sources or not answer:
            return []

        # Find all citation identifiers referenced in the LLM answer
        found_tags: List[str] = CITATION_TAG_PATTERN.findall(answer)
        if not found_tags:
            return []

        # Deduplicate referenced citation IDs
        referenced_cids: Set[str] = set(found_tags)

        # Validate against the available retrieved sources (S1..Sn)
        validated_citations: List[CitationItem] = []
        for idx, item in enumerate(sources, start=1):
            cid = f"S{idx}"
            # Only include citations that the LLM explicitly referenced AND Cogniva provided
            if cid in referenced_cids:
                filename = item.document_original_filename or item.document_filename
                validated_citations.append(
                    CitationItem(
                        citation_id=cid,
                        document_id=item.document_id,
                        document_filename=filename,
                        chunk_id=item.chunk_id,
                        chunk_index=item.chunk_index,
                        page_number=item.page_number,
                        similarity_score=item.similarity_score,
                        cosine_distance=item.cosine_distance,
                        metadata=item.metadata,
                    )
                )

        return validated_citations


citation_validator = CitationValidator()
