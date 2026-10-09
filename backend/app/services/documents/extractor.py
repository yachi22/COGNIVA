import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymupdf  # PyMuPDF
import docx  # python-docx
from pydantic import BaseModel, Field

from app.services.documents.cleaner import clean_extracted_text


class ExtractionError(Exception):
    """Raised when document extraction encounters an invalid or unreadable file."""
    pass


class ExtractedUnit(BaseModel):
    """
    Normalized unit of extracted content.
    Preserves provenance information required for future Phase 7 chunking and RAG citations.
    """
    unit_type: str = Field(..., description="'page' for PDF; 'paragraph', 'heading', 'table' for DOCX")
    page_number: Optional[int] = Field(None, description="1-indexed page number for PDFs; None for DOCX")
    sequence_number: int = Field(..., description="1-indexed sequence order within the document")
    text: str = Field(..., description="Normalized clean textual content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structural attributes (heading level, style, char count)")


class ExtractedDocument(BaseModel):
    """
    Normalized extracted representation of a document.
    """
    document_id: uuid.UUID
    file_type: str
    units: List[ExtractedUnit]
    total_pages: Optional[int] = None
    total_units: int
    total_characters: int
    total_words: int
    full_text: str
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PDFExtractor:
    """
    High-fidelity PDF extractor using PyMuPDF.
    Preserves exact 1-indexed page provenance.
    """

    def extract(self, file_path: Path, document_id: uuid.UUID) -> ExtractedDocument:
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF document: {str(e)}")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise ExtractionError("PDF document has 0 pages.")

        units: List[ExtractedUnit] = []
        try:
            for page_idx in range(total_pages):
                page = doc.load_page(page_idx)
                raw_text = page.get_text("text")
                cleaned_text = clean_extracted_text(raw_text)
                page_number = page_idx + 1

                # If page contains extractable text, create unit
                if cleaned_text:
                    unit = ExtractedUnit(
                        unit_type="page",
                        page_number=page_number,
                        sequence_number=len(units) + 1,
                        text=cleaned_text,
                        metadata={
                            "page_number": page_number,
                            "raw_chars": len(raw_text),
                            "clean_chars": len(cleaned_text),
                            "word_count": len(cleaned_text.split()),
                        },
                    )
                    units.append(unit)
        except Exception as e:
            raise ExtractionError(f"Error during PDF text extraction: {str(e)}")
        finally:
            doc.close()

        full_text = "\n\n".join(u.text for u in units)
        total_chars = len(full_text)
        total_words = len(full_text.split()) if full_text else 0

        return ExtractedDocument(
            document_id=document_id,
            file_type="pdf",
            units=units,
            total_pages=total_pages,
            total_units=len(units),
            total_characters=total_chars,
            total_words=total_words,
            full_text=full_text,
        )


class DOCXExtractor:
    """
    Structure-aware DOCX extractor using python-docx.
    Preserves headings, paragraphs, and tables with sequential order without fabricating page numbers.
    """

    def extract(self, file_path: Path, document_id: uuid.UUID) -> ExtractedDocument:
        try:
            doc = docx.Document(file_path)
        except Exception as e:
            raise ExtractionError(f"Failed to parse DOCX document: {str(e)}")

        units: List[ExtractedUnit] = []

        try:
            # 1. Extract paragraphs & headings
            for p_idx, paragraph in enumerate(doc.paragraphs):
                raw_text = paragraph.text
                cleaned = clean_extracted_text(raw_text)
                if not cleaned:
                    continue

                style_name = paragraph.style.name if paragraph.style else "Normal"
                is_heading = style_name.lower().startswith("heading")
                heading_level: Optional[int] = None
                if is_heading:
                    try:
                        heading_level = int(style_name.split()[-1])
                    except (ValueError, IndexError):
                        heading_level = 1

                unit = ExtractedUnit(
                    unit_type="heading" if is_heading else "paragraph",
                    page_number=None,  # Explicitly None for DOCX
                    sequence_number=len(units) + 1,
                    text=cleaned,
                    metadata={
                        "style": style_name,
                        "is_heading": is_heading,
                        "heading_level": heading_level,
                        "paragraph_index": p_idx,
                        "word_count": len(cleaned.split()),
                    },
                )
                units.append(unit)

            # 2. Extract tables
            for t_idx, table in enumerate(doc.tables):
                rows_text = []
                for row in table.rows:
                    cells = [clean_extracted_text(cell.text) for cell in row.cells]
                    # Filter empty cells and join
                    row_str = " | ".join(c for c in cells if c)
                    if row_str:
                        rows_text.append(row_str)

                if rows_text:
                    table_text = "\n".join(rows_text)
                    unit = ExtractedUnit(
                        unit_type="table",
                        page_number=None,
                        sequence_number=len(units) + 1,
                        text=table_text,
                        metadata={
                            "table_index": t_idx,
                            "row_count": len(rows_text),
                            "word_count": len(table_text.split()),
                        },
                    )
                    units.append(unit)

        except Exception as e:
            raise ExtractionError(f"Error extracting DOCX content: {str(e)}")

        full_text = "\n\n".join(u.text for u in units)
        total_chars = len(full_text)
        total_words = len(full_text.split()) if full_text else 0

        return ExtractedDocument(
            document_id=document_id,
            file_type="docx",
            units=units,
            total_pages=None,  # No synthetic page numbers
            total_units=len(units),
            total_characters=total_chars,
            total_words=total_words,
            full_text=full_text,
        )


class DocumentExtractor:
    """
    Unified extraction facade routing by file type.
    """

    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.docx_extractor = DOCXExtractor()

    def extract(self, file_path: Path, file_type: str, document_id: uuid.UUID) -> ExtractedDocument:
        norm_type = file_type.lower().strip()
        if norm_type == "pdf":
            return self.pdf_extractor.extract(file_path=file_path, document_id=document_id)
        elif norm_type == "docx":
            return self.docx_extractor.extract(file_path=file_path, document_id=document_id)
        else:
            raise ExtractionError(f"Unsupported file type for extraction: {file_type}")


# Singleton instance
document_extractor = DocumentExtractor()
