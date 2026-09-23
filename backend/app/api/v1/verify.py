from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile

from ...core.errors import ServiceNotReadyException
from ...schemas.common import (
    EvidencePreference,
    ExecutionMode,
    InputModality,
    ServiceNotReadyResponse,
    VerificationDepth,
)
from ...schemas.verify import TextVerifyRequest, UrlVerifyRequest
from ...services.input_processing.audio import audio_service
from ...services.input_processing.image import image_service
from ...services.input_processing.text import text_service
from ...services.input_processing.url import url_service

router = APIRouter(prefix="/verify", tags=["Verification Contracts"])


@router.post(
    "/text",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify Text Claim (Contract)",
)
async def verify_text(
    payload: TextVerifyRequest, request: Request
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for text claim verification.
    Phase 1: Strictly validates payload. Does NOT fabricate claims or verdicts.
    """
    text_service.validate_text(payload.text)
    raise ServiceNotReadyException(
        message="Text verification service is not implemented yet in Phase 1."
    )


@router.post(
    "/url",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify URL Claim (Contract)",
)
async def verify_url(
    payload: UrlVerifyRequest, request: Request
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for URL claim verification.
    Phase 1: Validates URL format. Does NOT scrape or fabricate evidence.
    """
    url_service.validate_url(str(payload.url))
    raise ServiceNotReadyException(
        message="URL verification service is not implemented yet in Phase 1."
    )


@router.post(
    "/image",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify Image Claim (Contract)",
)
async def verify_image(
    request: Request,
    file: UploadFile = File(..., description="Uploaded image screenshot/document"),
    depth: VerificationDepth = Form(default=VerificationDepth.STANDARD),
    mode: ExecutionMode = Form(default=ExecutionMode.LIVE),
    evidence_preference: EvidencePreference = Form(
        default=EvidencePreference.BALANCED
    ),
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for image/screenshot claim verification.
    Phase 1: Validates image size, MIME type, and extension. Does NOT run OCR or fake text.
    """
    image_service.validate_image(file)
    raise ServiceNotReadyException(
        message="Image OCR and visual claim verification service is not implemented yet in Phase 1."
    )


@router.post(
    "/audio",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify Audio Claim (Contract)",
)
async def verify_audio(
    request: Request,
    file: UploadFile = File(..., description="Uploaded audio recording"),
    depth: VerificationDepth = Form(default=VerificationDepth.STANDARD),
    mode: ExecutionMode = Form(default=ExecutionMode.LIVE),
    evidence_preference: EvidencePreference = Form(
        default=EvidencePreference.BALANCED
    ),
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for audio recording verification.
    Phase 1:
      - Validates MIME type
      - Validates file extension
      - Validates file size
      - Rejects empty files (0 bytes)
      - Rejects unsupported formats (415)
      - Does NOT run Whisper or Speech-to-Text
      - Does NOT fabricate transcripts, claims, or verdicts
    """
    audio_service.validate_audio(file)
    raise ServiceNotReadyException(
        message="Audio Speech-to-Text pipeline (Whisper) is not implemented yet in Phase 1."
    )
