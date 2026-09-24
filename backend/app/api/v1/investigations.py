import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException, ServiceNotReadyException
from ...database.repository import InvestigationRepository
from ...database.session import get_db
from ...schemas.claim import (
    ClaimDetailResponse,
    ClaimListResponse,
    ClaimTaskItem,
)
from ...schemas.common import (
    ExecutionMode,
    InputModality,
    ServiceNotReadyResponse,
)
from ...schemas.evidence import (
    EvidenceItem,
    EvidenceListResponse,
    SourceItem,
    SourceListResponse,
)
from ...schemas.investigation import (
    InvestigationCreateRequest,
    InvestigationDetailResponse,
    InvestigationStatusResponse,
)
from ...services.claim_extraction import claim_extraction_service
from ...services.rag import evidence_retrieval_service

router = APIRouter(prefix="/investigations", tags=["Investigation Contracts & Orchestration"])


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"


@router.post(
    "",
    response_model=InvestigationDetailResponse,
    status_code=201,
    summary="Create Investigation & Extract Claims",
)
async def create_investigation(
    payload: InvestigationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> InvestigationDetailResponse:
    """
    Creates an investigation pipeline, ingests the provided content,
    runs real agentic claim extraction & task generation, and optionally
    executes Phase 5 real web evidence retrieval.
    """
    request_id = get_request_id(request)

    depth_str = payload.depth.value if hasattr(payload.depth, "value") else str(payload.depth)
    mode_str = payload.mode.value if hasattr(payload.mode, "value") else str(payload.mode)
    modality_str = payload.modality.value if hasattr(payload.modality, "value") else str(payload.modality)
    pref_str = payload.evidence_preference.value if hasattr(payload.evidence_preference, "value") else str(payload.evidence_preference)

    inv = InvestigationRepository.create_investigation(
        db=db,
        input_type=modality_str,
        input_mode=mode_str,
        title=payload.title or (payload.content[:50] + "..." if payload.content else f"{modality_str} Investigation"),
        verification_depth=depth_str,
        evidence_preference=pref_str,
    )

    if payload.content:
        # Create input record
        InvestigationRepository.create_input(
            db=db,
            investigation_id=inv.id,
            input_type=modality_str,
            original_text=payload.content,
        )
        # Extract and persist atomic claims & tasks
        await claim_extraction_service.extract_and_persist(
            db=db,
            investigation_id=inv.id,
            raw_text=payload.content,
            language="en",
        )
        # Phase 5: Retrieve real web evidence dynamically if requested
        if payload.retrieve_evidence:
            await evidence_retrieval_service.retrieve_for_investigation(
                db=db,
                investigation_id=inv.id,
            )
        db.refresh(inv)

    return InvestigationDetailResponse(
        investigation_id=inv.id,
        title=inv.title,
        status=inv.status,
        modality=InputModality(inv.input_type),
        mode=ExecutionMode(inv.input_mode),
        created_at=inv.created_at.isoformat() if inv.created_at else None,
        claims_count=len(inv.claims),
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}",
    response_model=InvestigationDetailResponse,
    status_code=200,
    summary="Get Investigation Detail",
)
async def get_investigation(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> InvestigationDetailResponse:
    """
    Retrieves real investigation metadata, current lifecycle status, and claims count.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    return InvestigationDetailResponse(
        investigation_id=inv.id,
        title=inv.title,
        status=inv.status,
        modality=InputModality(inv.input_type),
        mode=ExecutionMode(inv.input_mode),
        created_at=inv.created_at.isoformat() if inv.created_at else None,
        claims_count=len(inv.claims),
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}/status",
    response_model=InvestigationStatusResponse,
    status_code=200,
    summary="Get Investigation Stage Progress",
)
async def get_investigation_status(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> InvestigationStatusResponse:
    """
    Tracks real investigation lifecycle stage progress.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    # Determine progress percent and current stage
    status_upper = inv.status.upper()
    if status_upper in ("TASKS_CREATED", "CLAIMS_EXTRACTED"):
        progress_percent = 40
        current_stage = "TASKS_CREATED"
    elif status_upper in ("READY_FOR_RETRIEVAL",):
        progress_percent = 50
        current_stage = "READY_FOR_RETRIEVAL"
    elif status_upper in ("RETRIEVING_EVIDENCE",):
        progress_percent = 65
        current_stage = "RETRIEVING_EVIDENCE"
    elif status_upper in ("READY_FOR_VERIFICATION",):
        progress_percent = 80
        current_stage = "READY_FOR_VERIFICATION"
    elif status_upper in ("NO_EVIDENCE_FOUND",):
        progress_percent = 80
        current_stage = "NO_EVIDENCE_FOUND"
    elif status_upper in ("RECEIVED", "PROCESSING"):
        progress_percent = 20
        current_stage = "INPUT_RECEIVED"
    elif status_upper in ("QUEUED",):
        progress_percent = 10
        current_stage = "QUEUED"
    elif status_upper in ("COMPLETED",):
        progress_percent = 100
        current_stage = "COMPLETED"
    elif status_upper in ("FAILED",):
        progress_percent = 100
        current_stage = "FAILED"
    else:
        progress_percent = 30
        current_stage = status_upper

    return InvestigationStatusResponse(
        investigation_id=inv.id,
        status=inv.status,
        progress_percent=progress_percent,
        current_stage=current_stage,
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}/claims",
    response_model=ClaimListResponse,
    status_code=200,
    summary="Get Extracted Investigation Claims & Tasks",
)
async def get_investigation_claims(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ClaimListResponse:
    """
    Retrieves real extracted atomic claims and their generated verification tasks.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
    claim_items: list[ClaimDetailResponse] = []

    for c in claims:
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
            for t in c.tasks
        ]
        claim_items.append(
            ClaimDetailResponse(
                id=c.id,
                investigation_id=c.investigation_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type or "OTHER",
                language=c.language,
                context=c.context,
                order_index=c.order_index,
                extraction_confidence=float(c.extraction_confidence) if c.extraction_confidence is not None else None,
                status=c.status,
                tasks=tasks,
                created_at=c.created_at.isoformat() if c.created_at else None,
            )
        )

    return ClaimListResponse(
        investigation_id=investigation_id,
        claims=claim_items,
        total=len(claim_items),
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}/evidence",
    response_model=EvidenceListResponse,
    status_code=200,
    summary="Get Investigation Retrieved Evidence",
)
async def get_investigation_evidence(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    """
    Retrieves real external evidence items dynamically discovered and ranked in Phase 5.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    evidence_models = InvestigationRepository.get_evidence_for_investigation(db, investigation_id)
    evidence_items = [
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
        investigation_id=inv.id,
        evidence=evidence_items,
        total=len(evidence_items),
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}/sources",
    response_model=SourceListResponse,
    status_code=200,
    summary="Get Investigation External Sources",
)
async def get_investigation_sources(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> SourceListResponse:
    """
    Retrieves distinct external web sources discovered and used in this investigation.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    sources = InvestigationRepository.get_sources_for_investigation(db, investigation_id)
    source_items = [
        SourceItem(
            source_id=str(s.id),
            url=s.url,
            title=s.title,
            publisher=s.publisher,
            domain=s.domain,
            source_type=s.source_type,
            author=s.author,
            publication_date=s.publication_date.isoformat() if s.publication_date else None,
            retrieved_date=s.retrieved_date.isoformat() if s.retrieved_date else None,
        )
        for s in sources
    ]

    return SourceListResponse(
        investigation_id=inv.id,
        sources=source_items,
        total=len(source_items),
        request_id=request_id,
    )


@router.post(
    "/{investigation_id}/retrieve-evidence",
    response_model=EvidenceListResponse,
    status_code=200,
    summary="Trigger Real Web Evidence Retrieval",
)
async def trigger_evidence_retrieval(
    investigation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    """
    Executes the real Web Search + RAG evidence retrieval pipeline for this investigation:
    Searches web, fetches sources, extracts text, chunks, embeds with 768-dim vectors,
    stores in Supabase pgvector, runs semantic vector retrieval, and ranks evidence.
    """
    request_id = get_request_id(request)
    inv = InvestigationRepository.get_investigation(db, investigation_id)
    if not inv:
        raise NotFoundException(
            message=f"Investigation '{investigation_id}' not found.",
            details={"investigation_id": investigation_id},
        )

    evidence_models = await evidence_retrieval_service.retrieve_for_investigation(
        db=db,
        investigation_id=investigation_id,
    )

    evidence_items = [
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
        investigation_id=inv.id,
        evidence=evidence_items,
        total=len(evidence_items),
        request_id=request_id,
    )


@router.get(
    "/{investigation_id}/timeline",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Get Investigation Timeline (Contract)",
)
async def get_investigation_timeline(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Timeline analysis is scheduled for Phase 6.
    """
    raise ServiceNotReadyException(
        message="Timeline analysis pipeline is scheduled for Phase 6."
    )


@router.post(
    "/{investigation_id}/copilot",
    response_model=ServiceNotReadyResponse,
    status_code=501,
    summary="Query AI Copilot for Investigation (Contract)",
)
async def query_investigation_copilot(
    investigation_id: str, request: Request
) -> ServiceNotReadyResponse:
    """
    Evidence-grounded Copilot is scheduled for Phase 7.
    """
    raise ServiceNotReadyException(
        message="Evidence-grounded AI Copilot is scheduled for Phase 7."
    )
