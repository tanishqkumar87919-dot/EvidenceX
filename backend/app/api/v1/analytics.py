from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...schemas.analytics import AnalyticsOverviewResponse
from ...services.analytics import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics & Global Intelligence"])


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=200,
    summary="Get Analytics Overview",
)
async def get_analytics_overview(
    request: Request,
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """
    Computes and aggregates real verification metrics, veracity trends,
    and source diversity strictly derived from persisted database records.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "req_analytics"
    return analytics_service.get_overview(db=db, request_id=request_id)
