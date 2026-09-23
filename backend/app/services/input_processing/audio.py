import hashlib
import io
import math
import os
import tempfile
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import av
from fastapi import UploadFile
from pydantic import BaseModel

from ...core.config import settings
from ...core.errors import BadRequestException, TranscriptionFailedException
from ...core.security import validate_uploaded_file
from ...schemas.common import ExecutionMode, InputModality
from ...schemas.ingest import NormalizedInput
from ..language import detect_language


def compute_bytes_hash(data: bytes) -> str:
    """Computes SHA-256 hash for binary audio content deduplication."""
    return hashlib.sha256(data).hexdigest()


class STTResult(BaseModel):
    transcript: str
    confidence: Optional[float] = None
    language: str = "UNKNOWN"
    duration: Optional[float] = None
    provider: str = "whisper"
    model: str = "tiny"


class STTProviderInterface(ABC):
    """
    Pluggable interface for Speech-to-Text providers.
    Ensures provider swapability (Whisper, Google STT, Deepgram, etc.)
    without modifying core business logic.
    """

    @abstractmethod
    def transcribe(self, temp_audio_path: str, original_filename: str) -> STTResult:
        """Transcribes audio from a safe temporary file path."""
        pass


AudioProcessorInterface = STTProviderInterface


class FasterWhisperSTTProvider(STTProviderInterface):
    """
    High-performance on-device Speech-to-Text provider powered by faster-whisper.
    Transcribes actual speech dynamically, computes real confidence metrics,
    and detects spoken language (English, Hindi, etc.).
    """

    _model_instance = None

    @classmethod
    def get_model(cls):
        if cls._model_instance is None:
            from faster_whisper import WhisperModel
            model_size = settings.WHISPER_MODEL or "tiny"
            cls._model_instance = WhisperModel(model_size, device="cpu", compute_type="int8")
        return cls._model_instance

    def transcribe(self, temp_audio_path: str, original_filename: str) -> STTResult:
        try:
            model = self.get_model()
            segments, info = model.transcribe(
                temp_audio_path,
                beam_size=5,
                vad_filter=True,
            )

            segment_list = list(segments)
            transcript_parts = [s.text.strip() for s in segment_list if s.text and s.text.strip()]
            full_transcript = " ".join(transcript_parts).strip()

            if not full_transcript:
                raise TranscriptionFailedException(
                    message="Audio transcription could not be completed (no recognizable speech detected).",
                )

            # Calculate confidence from avg_logprob: exp(logprob) clamped to [0, 1]
            confidences = [
                min(1.0, max(0.0, math.exp(s.avg_logprob)))
                for s in segment_list
                if hasattr(s, "avg_logprob") and s.avg_logprob is not None
            ]
            avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None

            # Language detected by Whisper
            detected_lang = info.language if info and hasattr(info, "language") and info.language else "UNKNOWN"

            return STTResult(
                transcript=full_transcript,
                confidence=avg_confidence,
                language=detected_lang,
                duration=round(info.duration, 2) if info and hasattr(info, "duration") and info.duration else None,
                provider="faster_whisper",
                model=settings.WHISPER_MODEL or "tiny",
            )
        except (BadRequestException, TranscriptionFailedException):
            raise
        except Exception as e:
            raise TranscriptionFailedException(
                message=f"Audio transcription could not be completed: {str(e)}",
            )


class AudioService:
    """
    Audio Ingestion & Transcription Service.
    Enforces format validation, duration/container integrity, safe temp file lifecycle,
    real Speech-to-Text transcription, and NormalizedInput generation.
    """

    def __init__(self):
        # Configurable provider (Whisper by default)
        self.provider: STTProviderInterface = FasterWhisperSTTProvider()

    def validate_audio(self, file: UploadFile) -> Tuple[bytes, Dict[str, Any]]:
        """
        Validates uploaded file against MIME types, extensions, size limits,
        and inspects the container with PyAV to confirm audio stream validity.
        """
        content = validate_uploaded_file(
            file=file,
            max_bytes=settings.MAX_AUDIO_SIZE_BYTES,
            allowed_mimes=settings.ALLOWED_AUDIO_MIME_TYPES,
            allowed_extensions=settings.ALLOWED_AUDIO_EXTENSIONS,
        )

        # Inspect container and audio streams using PyAV
        try:
            container = av.open(io.BytesIO(content))
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if not audio_streams:
                raise BadRequestException(
                    message="The uploaded file does not contain a valid audio stream.",
                    code="NO_AUDIO_STREAM",
                )

            stream = audio_streams[0]
            # Duration calculation: container.duration is in AV_TIME_BASE (microseconds)
            duration_sec = None
            if container.duration is not None and container.duration > 0:
                duration_sec = round(container.duration / 1_000_000, 2)
            elif stream.duration is not None and stream.time_base is not None:
                duration_sec = round(float(stream.duration * stream.time_base), 2)

            audio_info = {
                "duration": duration_sec,
                "sample_rate": stream.rate,
                "channels": stream.channels,
                "codec_name": stream.codec_context.name if stream.codec_context else None,
            }
        except BadRequestException:
            raise
        except Exception as e:
            raise BadRequestException(
                message=f"Uploaded audio file is corrupted or unreadable: {str(e)}",
                code="CORRUPTED_AUDIO",
            )

        return content, audio_info

    def process(
        self,
        file: UploadFile,
        investigation_id: Optional[str] = None,
        depth: str = "standard",
        mode: ExecutionMode = ExecutionMode.LIVE,
        evidence_preference: str = "balanced",
    ) -> NormalizedInput:
        """
        Processes uploaded audio:
        1. Validates upload & container
        2. Safely writes to randomized temporary file
        3. Executes real Speech-to-Text via configured provider
        4. Detects language
        5. Cleans up temp file
        6. Constructs NormalizedInput with Phase 2 audio fields
        """
        content, audio_info = self.validate_audio(file)

        _, ext = os.path.splitext(file.filename.lower() if file.filename else ".wav")
        content_hash = compute_bytes_hash(content)
        sanitized_ref = f"audio/{content_hash[:16]}{ext}"

        eff_inv_id = (
            investigation_id.strip()
            if investigation_id and investigation_id.strip()
            else f"inv_{uuid.uuid4().hex[:12]}"
        )

        # Secure temporary file creation with guaranteed unlink
        temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        temp_path = temp_file.name
        try:
            try:
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()

                # Execute real transcription
                stt_result = self.provider.transcribe(temp_path, file.filename)
            finally:
                # Clean temporary file immediately after transcription
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
        except TranscriptionFailedException as tfe:
            tfe.investigation_id = eff_inv_id
            raise tfe

        # Language refinement: If Whisper detected language is unknown/missing, use language detector
        lang = stt_result.language
        if not lang or lang == "UNKNOWN":
            lang = detect_language(stt_result.transcript)

        effective_duration = stt_result.duration or audio_info.get("duration")

        metadata = {
            "audio_filename": file.filename,
            "audio_mime_type": file.content_type,
            "audio_duration": effective_duration,
            "sample_rate": audio_info.get("sample_rate"),
            "channels": audio_info.get("channels"),
            "codec": audio_info.get("codec_name"),
            "stt_provider": stt_result.provider,
            "stt_model": stt_result.model,
            "depth": depth,
            "evidence_preference": evidence_preference,
        }

        return NormalizedInput(
            investigation_id=eff_inv_id,
            input_type=InputModality.AUDIO,
            input_mode=mode,
            text=stt_result.transcript,
            audio_reference=sanitized_ref,
            audio_transcript=stt_result.transcript,
            audio_transcription_confidence=stt_result.confidence,
            language=lang,
            metadata=metadata,
            content_hash=content_hash,
            received_at=datetime.now(timezone.utc),
        )


audio_service = AudioService()
