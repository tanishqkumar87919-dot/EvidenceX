from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.evidence import EvidenceItem

router = APIRouter(prefix="/evidence", tags=["Evidence Intelligence & Citations"])


@router.get(
    "/{evidence_id}",
    response_model=EvidenceItem,
    status_code=200,
    summary="Get Evidence Item Detail",
)
async def get_evidence(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EvidenceItem:
    """
    Retrieves a specific evidence item with its source citation, exact excerpt,
    candidate stance, and hybrid reliability score from the database.
    """
    ev = InvestigationRepository.get_evidence_by_id(db, evidence_id)
    if not ev:
        raise NotFoundException(
            message=f"Evidence item '{evidence_id}' was not found.",
            details={"evidence_id": evidence_id},
        )

    return EvidenceItem(
        evidence_id=str(ev.id),
        claim_id=str(ev.claim_id) if ev.claim_id else None,
        source_title=ev.source.title if ev.source and ev.source.title else (ev.source.url if ev.source else "External Source"),
        source_url=ev.source.url if ev.source else "",
        publisher=(ev.source.publisher or ev.source.domain or "Unknown") if ev.source else "Unknown",
        snippet=ev.exact_relevant_excerpt,
        stance=ev.relationship_type.lower() if ev.relationship_type else "inconclusive",
        reliability_score=float(ev.relevance) if ev.relevance is not None else None,
        published_date=ev.source.publication_date.isoformat() if ev.source and ev.source.publication_date else None,
    )
