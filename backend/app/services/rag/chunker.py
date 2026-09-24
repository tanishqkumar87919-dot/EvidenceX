from dataclasses import dataclass
from typing import List, Optional

from ...core.config import settings
from .extractor import ExtractedDocument


@dataclass
class EvidenceChunk:
    """A bounded, contextual passage of extracted evidence text ready for embedding."""
    chunk_index: int
    content: str
    heading: Optional[str]
    character_count: int
    token_count: int
    url: str


class EvidenceChunker:
    """
    Splits cleaned source document body text into overlapping, sentence-aware passages.
    Preserves document structure and context headings.
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or getattr(settings, "RAG_CHUNK_SIZE", 600)
        self.chunk_overlap = chunk_overlap or getattr(settings, "RAG_CHUNK_OVERLAP", 100)

    def chunk_document(self, doc: ExtractedDocument) -> List[EvidenceChunk]:
        text = doc.body_text.strip()
        if not text:
            return []

        # If document is already smaller than chunk size, return single chunk
        if len(text) <= self.chunk_size:
            return [
                EvidenceChunk(
                    chunk_index=0,
                    content=text,
                    heading=doc.headings[0] if doc.headings else None,
                    character_count=len(text),
                    token_count=len(text.split()),
                    url=doc.url,
                )
            ]

        # Break text into paragraphs or sentences
        raw_units = [p.strip() for p in text.split("\n\n") if p.strip()]
        # If single unit is larger than chunk_size, split by sentences
        if len(raw_units) == 1 and len(raw_units[0]) > self.chunk_size:
            import re
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_units[0]) if s.strip()]
            raw_units = sentences if sentences else [raw_units[0]]

        chunks: List[EvidenceChunk] = []
        current_text = ""
        current_heading = doc.headings[0] if doc.headings else None
        chunk_idx = 0

        for unit in raw_units:
            # Check if unit matches any heading
            for h in doc.headings:
                if h in unit:
                    current_heading = h
                    break

            if not current_text:
                current_text = unit
            elif len(current_text) + len(unit) + 1 <= self.chunk_size:
                current_text = current_text + " " + unit
            else:
                chunks.append(
                    EvidenceChunk(
                        chunk_index=chunk_idx,
                        content=current_text,
                        heading=current_heading,
                        character_count=len(current_text),
                        token_count=len(current_text.split()),
                        url=doc.url,
                    )
                )
                chunk_idx += 1

                # Retain overlap from end of current_text
                if len(current_text) > self.chunk_overlap:
                    overlap_seed = current_text[-self.chunk_overlap :].strip()
                    current_text = (overlap_seed + " " + unit).strip()
                else:
                    current_text = unit

        if current_text:
            chunks.append(
                EvidenceChunk(
                    chunk_index=chunk_idx,
                    content=current_text,
                    heading=current_heading,
                    character_count=len(current_text),
                    token_count=len(current_text.split()),
                    url=doc.url,
                )
            )

        return chunks


evidence_chunker = EvidenceChunker()
