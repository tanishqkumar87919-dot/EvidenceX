import hashlib
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from ...core.errors import BadRequestException
from ...schemas.common import ExecutionMode, InputModality
from ...schemas.ingest import NormalizedInput
from ...schemas.verify import TextVerifyRequest
from ..language import detect_language


def compute_content_hash(content: str) -> str:
    """Computes SHA-256 hash for content deduplication."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class TextService:
    """
    Real Text Ingestion Service for arbitrary user-submitted text.
    Handles single claims, paragraphs, news articles, and social media posts.
    Does NOT split claims yet (deferred to Phase 4).
    """

    MAX_TEXT_LENGTH = 50000

    def validate_text(self, text: str) -> str:
        if not text or not text.strip():
            raise BadRequestException(
                message="Text statement cannot be empty or whitespace.",
                code="EMPTY_TEXT",
            )
        cleaned = text.strip()
        if len(cleaned) < 3:
            raise BadRequestException(
                message="Text statement must be at least 3 characters long.",
                code="TEXT_TOO_SHORT",
            )
        if len(cleaned) > self.MAX_TEXT_LENGTH:
            raise BadRequestException(
                message=f"Text statement exceeds maximum allowed size of {self.MAX_TEXT_LENGTH} characters.",
                code="TEXT_TOO_LONG",
            )
        return cleaned

    def normalize_text(self, text: str) -> str:
        """Unicode NFC normalization and excessive whitespace reduction."""
        normalized = unicodedata.normalize("NFC", text.strip())
        # Replace multiple spaces/newlines with single uniform spacing while preserving paragraph boundaries
        paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
        return "\n\n".join(" ".join(p.split()) for p in paragraphs)

    def process(self, payload: TextVerifyRequest) -> NormalizedInput:
        """
        Validates, normalizes, detects language, and constructs NormalizedInput
        for text ingestion.
        """
        raw_text = self.validate_text(payload.text)
        normalized_text = self.normalize_text(raw_text)

        # Detect language (English, Hindi, or UNKNOWN)
        lang = detect_language(normalized_text)

        # Content hash
        content_hash = compute_content_hash(normalized_text)

        # Investigation ID
        eff_inv_id = (
            payload.investigation_id.strip()
            if payload.investigation_id and payload.investigation_id.strip()
            else f"inv_{uuid.uuid4().hex[:12]}"
        )

        metadata = {
            "char_count": len(normalized_text),
            "word_count": len(normalized_text.split()),
            "raw_length": len(raw_text),
            "depth": payload.depth.value if hasattr(payload.depth, "value") else str(payload.depth),
            "evidence_preference": payload.evidence_preference.value if hasattr(payload.evidence_preference, "value") else str(payload.evidence_preference),
        }

        return NormalizedInput(
            investigation_id=eff_inv_id,
            input_type=InputModality.TEXT,
            input_mode=payload.mode if isinstance(payload.mode, ExecutionMode) else ExecutionMode(payload.mode),
            text=normalized_text,
            language=lang,
            metadata=metadata,
            content_hash=content_hash,
            received_at=datetime.now(timezone.utc),
        )


text_service = TextService()
