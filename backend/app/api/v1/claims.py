from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.claim import ClaimDetailResponse, ClaimTaskItem

router = APIRouter(prefix="/claims", tags=["Claim Intelligence & Extraction"])


@router.get(
    "/{claim_id}",
    response_model=ClaimDetailResponse,
    status_code=200,
    summary="Get Atomic Claim Detail & Tasks",
)
async def get_claim(
    claim_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ClaimDetailResponse:
    """
    Retrieves an atomic claim and its associated verification task plan.
    Phase 4: Real atomic claim breakdown and generated verification queries.
    """
    claim = InvestigationRepository.get_claim(db, claim_id)
    if not claim:
        raise NotFoundException(
            message=f"Claim '{claim_id}' was not found.",
            details={"claim_id": claim_id},
        )

    tasks = [
        ClaimTaskItem(
            id=t.id,
            claim_id=t.claim_id,
            task_description=t.task_description,
            search_query=t.search_query,
            task_status=t.task_status,
            completion_time=t.completion_time.isoformat() if t.completion_time else None,
            created_at=t.created_at.isoformat() if t.created_at else None,
        )
        for t in claim.tasks
    ]

    return ClaimDetailResponse(
        id=claim.id,
        investigation_id=claim.investigation_id,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type or "OTHER",
        language=claim.language,
        context=claim.context,
        order_index=claim.order_index,
        extraction_confidence=float(claim.extraction_confidence) if claim.extraction_confidence is not None else None,
        status=claim.status,
        tasks=tasks,
        created_at=claim.created_at.isoformat() if claim.created_at else None,
    )
