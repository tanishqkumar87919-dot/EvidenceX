from fastapi import APIRouter, Request

from ...core.errors import ServiceNotReadyException
from ...schemas.common import ServiceNotReadyResponse

router = APIRouter(prefix="/timeline", tags=["Timeline Contracts"])


@router.get(
    "/{investigation_id}",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Timeline By ID (Contract)",
)
async def get_timeline(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving timeline events for an investigation.
    Phase 1: Returns service not ready. Do not fabricate timeline events or dates.
    """
    raise ServiceNotReadyException(
        message="Timeline event generator is not implemented yet in Phase 1."
    )
