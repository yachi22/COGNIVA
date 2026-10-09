from typing import List, Optional, Tuple
from app.core.config import settings
from app.schemas.retrieval import RetrievalResultItem


class ContextAssembler:
    """
    Assembles ranked retrieval results into structured, provenance-preserving evidence blocks.
    Enforces configurable character budget limits while prioritizing top-ranked chunks.
    Makes it explicit to LLMs that these blocks are passive source data, not system instructions.
    """

    def __init__(self, max_context_chars: Optional[int] = None):
        self.max_context_chars = max_context_chars or settings.MAX_CONTEXT_CHARS

    def assemble(
        self,
        results: List[RetrievalResultItem],
    ) -> Tuple[str, List[RetrievalResultItem]]:
        """
        Takes ranked RetrievalResultItem objects and formats them into a bounded evidence string.
        Returns:
            context_text: Formatted string containing clear evidence blocks.
            included_items: List of RetrievalResultItem objects that fit within the context budget.
        """
        if not results:
            return "NO_RELEVANT_SOURCES_FOUND", []

        blocks: List[str] = []
        included_items: List[RetrievalResultItem] = []
        current_length = 0

        for idx, item in enumerate(results, start=1):
            citation_id = f"S{idx}"
            page_str = str(item.page_number) if item.page_number is not None else "N/A"
            filename = item.document_original_filename or item.document_filename

            header = (
                f"[{citation_id}]\n"
                f"Document: {filename}\n"
                f"Page: {page_str}\n"
                f"Chunk: {item.chunk_index}\n"
                f"Similarity: {item.similarity_score:.4f}\n"
                f"Content:\n"
            )

            chunk_content = item.content.strip()
            full_block = f"{header}{chunk_content}\n"
            block_len = len(full_block)

            # If adding full block fits within budget, include completely
            if current_length + block_len <= self.max_context_chars:
                blocks.append(full_block)
                included_items.append(item)
                current_length += block_len
            else:
                # Context limit reached. Check if we can fit partial content cleanly without breaking metadata
                remaining_budget = self.max_context_chars - current_length - len(header) - len("\n... [truncated to fit context budget]\n")
                if remaining_budget > 150:
                    truncated_content = chunk_content[:remaining_budget] + "\n... [truncated to fit context budget]"
                    partial_block = f"{header}{truncated_content}\n"
                    blocks.append(partial_block)
                    included_items.append(item)
                # Stop adding lower-ranked chunks once budget is exhausted
                break

        assembled_text = "\n".join(blocks).strip()
        return assembled_text, included_items


# Singleton instance
context_assembler = ContextAssembler()
