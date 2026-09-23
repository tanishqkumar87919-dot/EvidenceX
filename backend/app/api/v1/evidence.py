from fastapi import APIRouter, Request

from ...core.errors import ServiceNotReadyException
from ...schemas.common import ServiceNotReadyResponse

router = APIRouter(prefix="/evidence", tags=["Evidence Contracts"])


@router.get(
    "/{evidence_id}",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Evidence Item Detail (Contract)",
)
async def get_evidence(
    evidence_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Contract for retrieving specific evidence item and citation details.
    Phase 1: Returns service not ready. No fake evidence item fabricated.
    """
    raise ServiceNotReadyException(
        message=f"Evidence retrieval store is not implemented yet in Phase 1."
    )
