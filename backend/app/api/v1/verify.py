import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.common import (
    EvidencePreference,
    ExecutionMode,
    VerificationDepth,
)
from ...schemas.ingest import IngestResponse
from ...schemas.verify import TextVerifyRequest, UrlVerifyRequest
from ...services.claim_extraction import claim_extraction_service
from ...services.input_processing.audio import audio_service
from ...services.input_processing.image import image_service
from ...services.input_processing.text import text_service
from ...services.input_processing.url import url_service

router = APIRouter(prefix="/verify", tags=["Verification Intake & Ingestion"])


def get_request_id(request: Request) -> str:
    """Helper to extract correlation request ID."""
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"


@router.post(
    "/text",
    response_model=IngestResponse,
    status_code=200,
    summary="Ingest Text Claim",
)
async def verify_text(
    payload: TextVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Intake and normalization endpoint for arbitrary user-provided text claims,
    paragraphs, article excerpts, and multi-sentence content.
    Phase 4: Real text ingestion, NFC normalization, language detection, DB persistence,
    and agentic claim extraction & task generation.
    """
    request_id = get_request_id(request)
    normalized = text_service.process(payload)

    depth_str = payload.depth.value if hasattr(payload.depth, "value") else str(payload.depth)
    pref_str = payload.evidence_preference.value if hasattr(payload.evidence_preference, "value") else str(payload.evidence_preference)

    inv, _ = InvestigationRepository.persist_normalized_input(
        db=db,
        normalized=normalized,
        verification_depth=depth_str,
        evidence_preference=pref_str,
    )

    # Phase 4: Agentic claim extraction & task generation
    extraction_result = await claim_extraction_service.extract_and_persist(
        db=db,
        investigation_id=inv.id,
        normalized=normalized,
    )

    safe_metadata = {
        **normalized.metadata,
        "claims_count": extraction_result.get("claims_count", 0),
        "tasks_count": extraction_result.get("tasks_count", 0),
        "claim_extraction_status": extraction_result.get("status", "tasks_created"),
    }

    return IngestResponse(
        investigation_id=inv.id,
        input_type="TEXT",
        input_mode=inv.input_mode,
        status="received",
        request_id=request_id,
        language=normalized.language,
        extracted_text=normalized.text,
        metadata=safe_metadata,
        created_at=inv.created_at,
    )


@router.post(
    "/url",
    response_model=IngestResponse,
    status_code=200,
    summary="Ingest URL Article/Claim",
)
async def verify_url(
    payload: UrlVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Intake endpoint for public web URLs with SSRF protection, safe redirect validation,
    HTML extraction, metadata parsing, DB persistence, and agentic claim extraction.
    """
    request_id = get_request_id(request)
    normalized = await url_service.process(payload)

    depth_str = payload.depth.value if hasattr(payload.depth, "value") else str(payload.depth)
    pref_str = payload.evidence_preference.value if hasattr(payload.evidence_preference, "value") else str(payload.evidence_preference)

    inv, _ = InvestigationRepository.persist_normalized_input(
        db=db,
        normalized=normalized,
        verification_depth=depth_str,
        evidence_preference=pref_str,
    )

    # Phase 4: Agentic claim extraction & task generation
    extraction_result = await claim_extraction_service.extract_and_persist(
        db=db,
        investigation_id=inv.id,
        normalized=normalized,
    )

    safe_metadata = {
        **normalized.metadata,
        "claims_count": extraction_result.get("claims_count", 0),
        "tasks_count": extraction_result.get("tasks_count", 0),
        "claim_extraction_status": extraction_result.get("status", "tasks_created"),
    }

    return IngestResponse(
        investigation_id=inv.id,
        input_type="URL",
        input_mode=inv.input_mode,
        status="received",
        request_id=request_id,
        language=normalized.language,
        extracted_text=normalized.text,
        metadata=safe_metadata,
        created_at=inv.created_at,
    )


@router.post(
    "/image",
    response_model=IngestResponse,
    status_code=200,
    summary="Ingest Image / Screenshot with OCR",
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
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Intake endpoint for image/screenshot claim verification.
    Phase 4: Real OCR text extraction (Tesseract), bounding boxes, confidence calculation,
    DB persistence, and agentic claim extraction.
    """
    request_id = get_request_id(request)
    depth_str = depth.value if hasattr(depth, "value") else str(depth)
    pref_str = evidence_preference.value if hasattr(evidence_preference, "value") else str(evidence_preference)

    normalized = image_service.process(
        file=file,
        investigation_id=investigation_id,
        depth=depth_str,
        mode=mode,
        evidence_preference=pref_str,
    )

    inv, _ = InvestigationRepository.persist_normalized_input(
        db=db,
        normalized=normalized,
        verification_depth=depth_str,
        evidence_preference=pref_str,
    )

    # Phase 4: Agentic claim extraction & task generation
    extraction_result = await claim_extraction_service.extract_and_persist(
        db=db,
        investigation_id=inv.id,
        normalized=normalized,
    )

    safe_metadata = {
        **normalized.metadata,
        "claims_count": extraction_result.get("claims_count", 0),
        "tasks_count": extraction_result.get("tasks_count", 0),
        "claim_extraction_status": extraction_result.get("status", "tasks_created"),
    }

    return IngestResponse(
        investigation_id=inv.id,
        input_type="IMAGE",
        input_mode=inv.input_mode,
        status="received",
        request_id=request_id,
        language=normalized.language,
        extracted_text=normalized.text,
        metadata=safe_metadata,
        created_at=inv.created_at,
    )


@router.post(
    "/audio",
    response_model=IngestResponse,
    status_code=200,
    summary="Ingest Audio Recording with Speech-to-Text",
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
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Intake endpoint for audio recording verification via multipart/form-data file upload.
    Phase 4: Real Speech-to-Text transcription (faster-whisper), language detection,
    DB persistence, and agentic claim extraction on the transcribed audio speech.
    """
    request_id = get_request_id(request)
    depth_str = depth.value if hasattr(depth, "value") else str(depth)
    pref_str = evidence_preference.value if hasattr(evidence_preference, "value") else str(evidence_preference)

    normalized = audio_service.process(
        file=file,
        investigation_id=investigation_id,
        depth=depth_str,
        mode=mode,
        evidence_preference=pref_str,
    )

    inv, input_rec = InvestigationRepository.persist_normalized_input(
        db=db,
        normalized=normalized,
        verification_depth=depth_str,
        evidence_preference=pref_str,
    )

    # Phase 4: Agentic claim extraction & task generation
    extraction_result = await claim_extraction_service.extract_and_persist(
        db=db,
        investigation_id=inv.id,
        normalized=normalized,
    )

    safe_metadata = {
        **normalized.metadata,
        "claims_count": extraction_result.get("claims_count", 0),
        "tasks_count": extraction_result.get("tasks_count", 0),
        "claim_extraction_status": extraction_result.get("status", "tasks_created"),
    }

    return IngestResponse(
        investigation_id=inv.id,
        input_type="AUDIO",
        input_mode=inv.input_mode,
        status="received",
        request_id=request_id,
        language=normalized.language,
        extracted_text=normalized.text,
        audio_transcript=normalized.audio_transcript,
        metadata=safe_metadata,
        created_at=inv.created_at,
    )
