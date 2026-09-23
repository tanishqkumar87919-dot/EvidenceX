from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from .common import ExecutionMode, InputModality


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class NormalizedInput(BaseModel):
    """
    Standard normalized internal representation for all ingested inputs
    (TEXT, IMAGE, URL, AUDIO) entering the EvidenceX pipeline.
    """
    investigation_id: str = Field(..., description="Unique investigation identifier.")
    input_type: InputModality = Field(..., description="Input modality (TEXT, IMAGE, URL, AUDIO).")
    input_mode: ExecutionMode = Field(default=ExecutionMode.LIVE, description="Execution mode: LIVE (default) or DEMO.")
    text: Optional[str] = Field(default=None, description="Raw or normalized textual content.")
    url: Optional[str] = Field(default=None, description="Source URL for web ingestion.")
    image_reference: Optional[str] = Field(default=None, description="Sanitized storage reference for image uploads.")
    audio_reference: Optional[str] = Field(default=None, description="Sanitized storage reference for audio uploads.")
    audio_transcript: Optional[str] = Field(default=None, description="Transcribed speech from uploaded audio.")
    audio_transcription_confidence: Optional[float] = Field(default=None, description="Confidence score of speech transcription.")
    language: str = Field(default="UNKNOWN", description="Detected language code (e.g. 'en', 'hi', or 'UNKNOWN').")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe processing metadata (dimensions, duration, headers, etc.).")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 hash for deduplication and audit integrity.")
    received_at: datetime = Field(default_factory=now_utc, description="Timestamp when input was received.")


class IngestResponse(BaseModel):
    """
    Client response model returned after successful ingestion of arbitrary user inputs.
    Contains essential investigation metadata without leaking credentials or private filesystem paths.
    """
    investigation_id: str = Field(..., description="ID of the investigation associated with this input.")
    input_type: str = Field(..., description="Modality of the ingested input: TEXT, IMAGE, URL, AUDIO.")
    input_mode: str = Field(default="LIVE", description="Execution mode: LIVE (default) or DEMO.")
    status: str = Field(default="received", description="Current status of the investigation / input.")
    request_id: str = Field(..., description="Unique correlation request ID.")
    language: str = Field(default="UNKNOWN", description="Detected language of input content.")
    extracted_text: Optional[str] = Field(default=None, description="Extracted article/image/text content.")
    audio_transcript: Optional[str] = Field(default=None, description="Speech-to-Text transcript for audio inputs.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe metadata (excluding internal paths/keys).")
    created_at: datetime = Field(default_factory=now_utc, description="Ingestion timestamp.")
