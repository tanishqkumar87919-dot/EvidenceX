import uuid
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
    Phase 1: Validates payload bounds. Preserves request_id, investigation_id, input_type=TEXT, input_mode.
    Does NOT fabricate claims or verdicts.
    """
    text_service.validate_text(payload.text)
    investigation_id = payload.investigation_id or f"inv_{uuid.uuid4().hex[:12]}"
    mode_str = payload.mode.value if hasattr(payload.mode, "value") else str(payload.mode)
    raise ServiceNotReadyException(
        message="Text verification service is not implemented yet in Phase 1.",
        investigation_id=investigation_id,
        input_type="TEXT",
        input_mode=mode_str,
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
    Phase 1: Validates URL format. Preserves request_id, investigation_id, input_type=URL, input_mode.
    Does NOT scrape or fabricate evidence.
    """
    url_service.validate_url(str(payload.url))
    investigation_id = payload.investigation_id or f"inv_{uuid.uuid4().hex[:12]}"
    mode_str = payload.mode.value if hasattr(payload.mode, "value") else str(payload.mode)
    raise ServiceNotReadyException(
        message="URL verification service is not implemented yet in Phase 1.",
        investigation_id=investigation_id,
        input_type="URL",
        input_mode=mode_str,
    )


@router.post(
    "/image",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify Image Claim (Contract)",
)
async def verify_image(
    request: Request,
    file: UploadFile = File(..., description="Uploaded image screenshot or document (multipart/form-data)"),
    investigation_id: Optional[str] = Form(default=None, description="Optional investigation ID to associate"),
    depth: VerificationDepth = Form(default=VerificationDepth.STANDARD),
    mode: ExecutionMode = Form(default=ExecutionMode.LIVE),
    evidence_preference: EvidencePreference = Form(
        default=EvidencePreference.BALANCED
    ),
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for image/screenshot claim verification.
    Phase 1: Validates image size, MIME type, and extension. Preserves request_id, investigation_id, input_type=IMAGE, input_mode.
    Does NOT run OCR or fake text.
    """
    image_service.validate_image(file)
    eff_inv_id = (
        investigation_id.strip()
        if investigation_id and investigation_id.strip()
        else f"inv_{uuid.uuid4().hex[:12]}"
    )
    mode_str = mode.value if hasattr(mode, "value") else str(mode)
    raise ServiceNotReadyException(
        message="Image OCR and visual claim verification service is not implemented yet in Phase 1.",
        investigation_id=eff_inv_id,
        input_type="IMAGE",
        input_mode=mode_str,
    )


@router.post(
    "/audio",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Verify Audio Claim (Multipart Form Contract)",
)
async def verify_audio(
    request: Request,
    file: UploadFile = File(
        ...,
        description="Uploaded audio recording file (multipart/form-data: wav, mp3, mp4, m4a, webm, ogg, flac)",
    ),
    investigation_id: Optional[str] = Form(
        default=None,
        description="Optional client-provided investigation ID to preserve",
    ),
    depth: VerificationDepth = Form(
        default=VerificationDepth.STANDARD,
        description="Verification depth level (quick, standard, deep)",
    ),
    mode: ExecutionMode = Form(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO",
    ),
    evidence_preference: EvidencePreference = Form(
        default=EvidencePreference.BALANCED,
        description="Preferred evidence source weighting (balanced, official)",
    ),
) -> ServiceNotReadyResponse:
    """
    Intake endpoint for audio recording verification via multipart/form-data file upload.
    
    Phase 1 Requirements:
      - Multipart upload contract (UploadFile / Form)
      - MIME validation
      - Extension validation
      - File size validation
      - Empty file validation (rejects 0 bytes with HTTP 400)
      - Unsupported format validation (rejects unsupported formats with HTTP 415)
      - Strictly does NOT perform Whisper or Speech-to-Text processing
      - Strictly does NOT generate a transcript
      - Preserves:
          * request_id
          * investigation_id (preserves client ID or assigns unique identifier)
          * input_type = AUDIO
          * input_mode = LIVE by default (or requested mode)
      - Returns transparent SERVICE_NOT_READY structured response upon successful validation
    """
    # 1. Enforce strict upload validations
    audio_service.validate_audio(file)

    # 2. Preserve or generate investigation ID
    effective_investigation_id = (
        investigation_id.strip()
        if investigation_id and investigation_id.strip()
        else f"inv_{uuid.uuid4().hex[:12]}"
    )
    effective_mode = mode.value if hasattr(mode, "value") else str(mode)

    # 3. Transparent SERVICE_NOT_READY response preserving all required metadata
    raise ServiceNotReadyException(
        message="Audio Speech-to-Text pipeline (Whisper) is not implemented yet in Phase 1.",
        investigation_id=effective_investigation_id,
        input_type="AUDIO",
        input_mode=effective_mode,
    )
