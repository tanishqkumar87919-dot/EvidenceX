from typing import Any, Dict
from ...core.errors import BadRequestException, ServiceNotReadyException


class TextService:
    """
    Text verification service abstraction.
    In Phase 1: Validates content length and bounds without fabricating claims or verdicts.
    """

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
        return cleaned

    def process(self, text: str, mode: str = "LIVE") -> Dict[str, Any]:
        self.validate_text(text)
        # Phase 1: Do NOT implement LLM claim extraction / verification
        raise ServiceNotReadyException(
            message="Text verification service is not implemented yet in Phase 1."
        )


text_service = TextService()
