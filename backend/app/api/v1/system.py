from typing import Any, Dict
from fastapi import APIRouter, Request

from ...core.config import settings

router = APIRouter(prefix="/system", tags=["System Status"])


@router.get("/status", summary="System & Architecture Readiness Status")
async def get_system_status(request: Request) -> Dict[str, Any]:
    """
    Returns high-level system and service readiness information.
    Strict Security Guarantee:
      - Strictly NO API keys
      - Strictly NO tokens
      - Strictly NO passwords
      - Strictly NO database credentials or connection strings
      - Strictly NO internal environment values
    """
    request_id = getattr(request.state, "request_id", "unknown-request-id")
    has_supabase = bool(settings.SUPABASE_URL and (settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY))
    has_db = bool(settings.DATABASE_URL)

    return {
        "status": "operational",
        "service": "EvidenceX Backend",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "default_mode": settings.DEFAULT_MODE,
        "supported_modalities": ["TEXT", "IMAGE", "URL", "AUDIO"],
        "subsystems": {
            "api_gateway": "operational",
            "database_schema": "phase_2_ready",
            "input_ingestion": "phase_3_ready",
            "supabase_integration": "configured" if has_supabase else "unconfigured",
            "postgres_integration": "configured" if has_db else "unconfigured",
            "speech_to_text": "phase_3_ready",
            "ocr_vision": "phase_3_ready",
            "claim_extractor": "phase_1_contract_only",
            "evidence_retrieval": "phase_1_contract_only",
            "nli_verifier": "phase_1_contract_only",
        },
        "limits": {
            "max_audio_mb": round(settings.MAX_AUDIO_SIZE_BYTES / (1024 * 1024), 1),
            "max_image_mb": round(settings.MAX_IMAGE_SIZE_BYTES / (1024 * 1024), 1),
        },
        "request_id": request_id,
    }
