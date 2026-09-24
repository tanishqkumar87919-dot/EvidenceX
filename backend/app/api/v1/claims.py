from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.claim import ClaimDetailResponse, ClaimTaskItem
from ...schemas.evidence import EvidenceItem, EvidenceListResponse
from ...schemas.verification import (
    ClaimVerificationDetailResponse,
    ClaimVerificationResultItem,
)


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


@router.get(
    "/{claim_id}/evidence",
    response_model=EvidenceListResponse,
    status_code=200,
    summary="Get Evidence for Atomic Claim",
)
async def get_claim_evidence(
    claim_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    """
    Retrieves ranked evidence items specifically attached to this atomic claim.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "req_claim_ev"
    claim = InvestigationRepository.get_claim(db, claim_id)
    if not claim:
        raise NotFoundException(
            message=f"Claim '{claim_id}' was not found.",
            details={"claim_id": claim_id},
        )

    evidence_models = InvestigationRepository.get_evidence_for_claim(db, claim_id)
    items = [
        EvidenceItem(
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
        for ev in evidence_models
    ]

    return EvidenceListResponse(
        investigation_id=str(claim.investigation_id),
        evidence=items,
        total=len(items),
        request_id=request_id,
    )


@router.get(
    "/{claim_id}/verification",
    response_model=ClaimVerificationDetailResponse,
    status_code=200,
    summary="Get Single Claim Verification Result",
)
async def get_claim_verification(
    claim_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ClaimVerificationDetailResponse:
    """
    Retrieves the persisted verification result and grounded rationale for a specific claim.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "req_default"
    claim = InvestigationRepository.get_claim(db, claim_id)
    if not claim:
        raise NotFoundException(
            message=f"Claim '{claim_id}' was not found.",
            details={"claim_id": claim_id},
        )

    result = InvestigationRepository.get_verification_result_for_claim(db, claim_id)
    result_item = None
    if result:
        result_item = ClaimVerificationResultItem(
            verification_id=str(result.id),
            claim_id=str(result.claim_id),
            claim_text=claim.claim_text,
            verdict=result.verdict,
            confidence=float(result.model_confidence) if result.model_confidence is not None else 0.85,
            evidence_sufficiency=result.evidence_sufficiency or "MEDIUM",
            evidence_strength=float(result.evidence_strength) if result.evidence_strength is not None else 0.75,
            explanation=result.explanation or "",
            supporting_evidence_ids=[str(eid) for eid in (result.supporting_evidence_ids or [])],
            contradicting_evidence_ids=[str(eid) for eid in (result.contradicting_evidence_ids or [])],
            uncertainty=result.uncertainty,
            model_provider=result.model_provider,
            created_at=result.created_at.isoformat() if result.created_at else result.generated_timestamp.isoformat(),
        )

    return ClaimVerificationDetailResponse(
        claim_id=claim.id,
        investigation_id=claim.investigation_id,
        result=result_item,
        request_id=request_id,
    )
