from typing import Any, Dict
from fastapi import APIRouter, Request

router = APIRouter(prefix="/analytics", tags=["Analytics Contracts"])


@router.get(
    "/overview",
    summary="Get Analytics Overview (Contract)",
)
async def get_analytics_overview(request: Request) -> Dict[str, Any]:
    """
    Contract for aggregated verification metrics, veracity trends, and source diversity.
    Phase 1: Returns transparent empty/not-ready response. Strictly does NOT invent fake numbers.
    """
    request_id = getattr(request.state, "request_id", "unknown-request-id")
    return {
        "status": "service_not_ready",
        "message": "Analytics metrics are not available yet. Database layer is not initialized in Phase 1.",
        "request_id": request_id,
        "data": None,
    }
