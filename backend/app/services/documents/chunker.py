import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.documents.extractor import ExtractedDocument, ExtractedUnit


class ChunkData(BaseModel):
    """
    Structured representation of a document chunk before database persistence.
    """
    chunk_index: int = Field(..., description="0-indexed deterministic sequence order within document")
    content: str = Field(..., description="Clean textual content of chunk")
    page_number: Optional[int] = Field(None, description="1-indexed page number for PDFs; None for DOCX")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provenance and structural metadata")


class DocumentChunker:
    """
    Deterministic chunking service for Cogniva knowledge ingestion.
    Preserves document provenance (page numbers, heading levels, unit types, sequence)
    and splits on natural boundaries without unnecessarily breaking words.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: Optional[int] = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.min_chunk_size = min_chunk_size or settings.MIN_CHUNK_SIZE
        self.version = "1.0.0"

    def split_text_with_overlap(self, text: str) -> List[str]:
        """
        Splits text that exceeds chunk_size into overlapping segments.
        Respects paragraph, sentence, and word boundaries.
        """
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # If we are not at the very end of the text, seek a natural boundary
            if end < text_len:
                # Look backwards for a boundary in order of preference: paragraph break, line break, sentence, word
                sub = text[start:end]
                split_pos = -1

                for separator in ["\n\n", "\n", ". ", "? ", "! ", " "]:
                    pos = sub.rfind(separator)
                    # Don't pick a boundary that is too close to the start (keep at least half chunk_size)
                    if pos > self.chunk_size // 3:
                        split_pos = pos + len(separator)
                        break

                if split_pos > 0:
                    end = start + split_pos

            chunk_str = text[start:end].strip()
            if len(chunk_str) >= self.min_chunk_size or not chunks:
                chunks.append(chunk_str)

            # Advance with overlap
            if end >= text_len:
                break
            start = max(start + 1, end - self.chunk_overlap)

        return chunks

    def chunk_document(self, extracted_doc: ExtractedDocument) -> List[ChunkData]:
        """
        Takes normalized ExtractedDocument from Phase 6 and yields structured chunks
        with deterministic chunk_index and complete provenance metadata.
        """
        chunks: List[ChunkData] = []
        doc_id_str = str(extracted_doc.document_id)

        for unit in extracted_doc.units:
            unit_text = unit.text.strip()
            if not unit_text:
                continue

            # If unit fits inside chunk_size, keep it intact to preserve natural boundaries
            if len(unit_text) <= self.chunk_size:
                unit_chunks = [unit_text]
            else:
                unit_chunks = self.split_text_with_overlap(unit_text)

            for chunk_content in unit_chunks:
                clean_content = chunk_content.strip()
                if not clean_content:
                    continue

                chunk_index = len(chunks)
                chunk_meta: Dict[str, Any] = {
                    "document_id": doc_id_str,
                    "chunk_index": chunk_index,
                    "page_number": unit.page_number,
                    "unit_type": unit.unit_type,
                    "heading_level": unit.metadata.get("heading_level"),
                    "source_sequence": unit.sequence_number,
                    "char_count": len(clean_content),
                    "word_count": len(clean_content.split()),
                    "chunker_version": self.version,
                    "chunk_size_config": self.chunk_size,
                    "chunk_overlap_config": self.chunk_overlap,
                }

                # Include any additional structural metadata from unit
                if unit.metadata.get("style"):
                    chunk_meta["style"] = unit.metadata["style"]

                chunk = ChunkData(
                    chunk_index=chunk_index,
                    content=clean_content,
                    page_number=unit.page_number,
                    metadata=chunk_meta,
                )
                chunks.append(chunk)

        return chunks


# Singleton instance
document_chunker = DocumentChunker()
