from fastapi import APIRouter, Request

from ...core.errors import ServiceNotReadyException
from ...schemas.common import ServiceNotReadyResponse
from ...schemas.copilot import CopilotQueryRequest

router = APIRouter(prefix="/copilot", tags=["Copilot Contracts"])


@router.post(
    "",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Query AI Copilot (Contract)",
)
async def query_copilot(
    payload: CopilotQueryRequest, request: Request
) -> ServiceNotReadyResponse:
    """
    Direct contract for evidence-grounded AI copilot inquiry.
    Phase 1: Must not pretend to know evidence that does not exist. Returns service not ready.
    """
    raise ServiceNotReadyException(
        message="Evidence-grounded AI Copilot is not implemented yet in Phase 1."
    )


@router.post(
    "/{investigation_id}",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Query AI Copilot for Investigation (Contract)",
)
async def query_copilot_investigation(
    investigation_id: str, payload: CopilotQueryRequest, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for evidence-grounded AI copilot investigation query.
    Phase 1: Must not pretend to know evidence that does not exist. Returns service not ready.
    """
    raise ServiceNotReadyException(
        message="Evidence-grounded AI Copilot is not implemented yet in Phase 1."
    )
