from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import UploadFile

from ...core.config import settings
from ...core.errors import ServiceNotReadyException
from ...core.security import validate_uploaded_file


class AudioProcessorInterface(ABC):
    """
    Provider-agnostic interface for future Speech-to-Text and Audio processing.
    Ensures provider swapability (Whisper local, Whisper API, Deepgram, Google STT).
    """

    @abstractmethod
    def validate_audio(self, file: UploadFile) -> bytes:
        """Validates uploaded audio MIME type, extension, size, and non-emptiness."""
        pass

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Future Phase: Transcribes audio to text."""
        pass


class AudioService(AudioProcessorInterface):
    """
    Audio verification service abstraction.
    In Phase 1: Strictly enforces file validation without faking transcripts or claims.
    """

    def validate_audio(self, file: UploadFile) -> bytes:
        return validate_uploaded_file(
            file=file,
            max_bytes=settings.MAX_AUDIO_SIZE_BYTES,
            allowed_mimes=settings.ALLOWED_AUDIO_MIME_TYPES,
            allowed_extensions=settings.ALLOWED_AUDIO_EXTENSIONS,
        )

    async def transcribe(self, audio_bytes: bytes, filename: str) -> Dict[str, Any]:
        # Phase 1: Do NOT implement Whisper, do NOT generate fake transcripts
        raise ServiceNotReadyException(
            message="Audio Speech-to-Text pipeline (Whisper) is not implemented yet in Phase 1."
        )


audio_service = AudioService()
