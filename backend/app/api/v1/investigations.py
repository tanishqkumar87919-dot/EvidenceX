from fastapi import APIRouter, Request

from ...core.errors import ServiceNotReadyException
from ...schemas.common import ServiceNotReadyResponse
from ...schemas.investigation import (
    InvestigationCreateRequest,
    InvestigationDetailResponse,
    InvestigationStatusResponse,
)

router = APIRouter(prefix="/investigations", tags=["Investigation Contracts"])


@router.post(
    "",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Create Investigation (Contract)",
)
async def create_investigation(
    payload: InvestigationCreateRequest, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for creating a multi-agent investigation pipeline.
    Phase 1: Validates request format. Does NOT execute agentic investigations.
    """
    raise ServiceNotReadyException(
        message="Investigation orchestration pipeline is not implemented yet in Phase 1."
    )


@router.get(
    "/{investigation_id}",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Detail (Contract)",
)
async def get_investigation(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving investigation details.
    Phase 1: Returns service not ready. No fake investigation is fabricated.
    """
    raise ServiceNotReadyException(
        message=f"Investigation data store is not implemented yet in Phase 1."
    )


@router.get(
    "/{investigation_id}/status",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Status (Contract)",
)
async def get_investigation_status(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for tracking live investigation stage progress.
    Phase 1: Returns service not ready. No fake progress stages fabricated.
    """
    raise ServiceNotReadyException(
        message="Investigation status tracker is not implemented yet in Phase 1."
    )


@router.get(
    "/{investigation_id}/claims",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Claims (Contract)",
)
async def get_investigation_claims(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving atomic claims associated with an investigation.
    Phase 1: Returns service not ready. No fake claims fabricated.
    """
    raise ServiceNotReadyException(
        message="Claim extraction store is not implemented yet in Phase 1."
    )


@router.get(
    "/{investigation_id}/evidence",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Evidence (Contract)",
)
async def get_investigation_evidence(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving evidence items associated with an investigation.
    Phase 1: Returns service not ready. No fake evidence fabricated.
    """
    raise ServiceNotReadyException(
        message="Evidence retrieval store is not implemented yet in Phase 1."
    )


@router.get(
    "/{investigation_id}/timeline",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Timeline (Contract)",
)
async def get_investigation_timeline(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving temporal evolution events for an investigation.
    Phase 1: Returns service not ready. Do not fabricate timeline events or dates.
    """
    raise ServiceNotReadyException(
        message="Timeline event generator is not implemented yet in Phase 1."
    )


@router.post(
    "/{investigation_id}/copilot",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Query AI Copilot for Investigation (Contract)",
)
async def query_investigation_copilot(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for evidence-grounded AI copilot inquiries.
    Phase 1: Must not pretend to know evidence that does not exist. Returns service not ready.
    """
    raise ServiceNotReadyException(
        message="Evidence-grounded AI Copilot is not implemented yet in Phase 1."
    )



