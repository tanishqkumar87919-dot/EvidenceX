from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.evidence import (
    AssociatedClaimItem,
    AssociatedVerificationResultItem,
    EvidenceDetailResponse,
    SourceItem,
)

router = APIRouter(prefix="/evidence", tags=["Evidence Intelligence & Citations"])


@router.get(
    "/{evidence_id}",
    response_model=EvidenceDetailResponse,
    status_code=200,
    summary="Get Evidence Item Detail",
)
async def get_evidence(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EvidenceDetailResponse:
    """
    Retrieves a specific evidence item with its full excerpt, source citation,
    relevance score, candidate stance, and associated claims and verification results.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "req_evidence"
    ev = InvestigationRepository.get_evidence_by_id(db, evidence_id)
    if not ev:
        raise NotFoundException(
            message=f"Evidence item '{evidence_id}' was not found.",
            details={"evidence_id": evidence_id},
        )

    # Resolve associated claims
    claim_ids = set()
    if ev.claim_id:
        claim_ids.add(str(ev.claim_id))
    for assoc in getattr(ev, "claim_associations", []):
        if assoc.claim_id:
            claim_ids.add(str(assoc.claim_id))

    associated_claims = []
    associated_verifications = []

    for cid in claim_ids:
        c = InvestigationRepository.get_claim(db, cid)
        if c:
            v_res = InvestigationRepository.get_verification_result_for_claim(db, cid)
            associated_claims.append(
                AssociatedClaimItem(
                    claim_id=str(c.id),
                    claim_text=c.claim_text,
                    claim_type=c.claim_type,
                    verdict=v_res.verdict if v_res else None,
                )
            )
            if v_res:
                associated_verifications.append(
                    AssociatedVerificationResultItem(
                        verification_result_id=str(v_res.id),
                        verdict=v_res.verdict,
                        confidence=float(v_res.model_confidence) if v_res.model_confidence is not None else None,
                        explanation=v_res.explanation,
                    )
                )

    source_item = None
    if ev.source:
        source_item = SourceItem(
            source_id=str(ev.source.id),
            url=ev.source.url,
            title=ev.source.title,
            publisher=ev.source.publisher,
            domain=ev.source.domain,
            source_type=ev.source.source_type,
            author=ev.source.author,
            publication_date=ev.source.publication_date.isoformat() if ev.source.publication_date else None,
            retrieved_date=ev.source.retrieved_date.isoformat() if ev.source.retrieved_date else None,
            credibility_score=float(ev.relevance) if ev.relevance is not None else None,
        )

    rel = float(ev.relevance) if ev.relevance is not None else None
    return EvidenceDetailResponse(
        evidence_id=str(ev.id),
        claim_id=str(ev.claim_id) if ev.claim_id else (list(claim_ids)[0] if claim_ids else None),
        source_title=ev.source.title if ev.source and ev.source.title else (ev.source.url if ev.source else "External Source"),
        source_url=ev.source.url if ev.source else "",
        publisher=(ev.source.publisher or ev.source.domain or "Unknown") if ev.source else "Unknown",
        snippet=ev.exact_relevant_excerpt,
        excerpt=ev.exact_relevant_excerpt,
        stance=ev.relationship_type.lower() if ev.relationship_type else "inconclusive",
        reliability_score=rel,
        relevance_score=rel,
        published_date=ev.source.publication_date.isoformat() if ev.source and ev.source.publication_date else None,
        created_at=ev.created_at.isoformat() if ev.created_at else None,
        source=source_item,
        associated_claims=associated_claims,
        associated_verification_results=associated_verifications,
        request_id=request_id,
    )
