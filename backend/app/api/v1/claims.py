from fastapi import APIRouter, Request

from ...core.errors import ServiceNotReadyException
from ...schemas.common import ServiceNotReadyResponse

router = APIRouter(prefix="/claims", tags=["Claim Contracts"])


@router.get(
    "/{claim_id}",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Claim Detail (Contract)",
)
async def get_claim(claim_id: str, request: Request) -> ServiceNotReadyResponse:
    """
    Contract for retrieving an atomic claim breakdown and assessment.
    Phase 1: Returns service not ready. No fake claim or verdict fabricated.
    """
    raise ServiceNotReadyException(
        message=f"Claim intelligence store is not implemented yet in Phase 1."
    )
