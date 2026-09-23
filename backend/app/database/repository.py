import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AgentEventModel,
    ClaimEvidenceModel,
    ClaimModel,
    ClaimTaskModel,
    CopilotMessageModel,
    EvidenceModel,
    InputModel,
    InvestigationModel,
    SourceModel,
    TimelineEventModel,
    UserModel,
    UserSettingModel,
    VerificationResultModel,
    now_utc,
)


def compute_content_hash(content: str) -> str:
    """Computes SHA-256 hash for content deduplication."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class InvestigationRepository:
    """
    Data Access Layer strictly enforcing investigation data isolation.
    Every query is explicitly scoped to avoid cross-investigation leakage.
    """

    @staticmethod
    def create_investigation(
        db: Session,
        input_type: str,
        input_mode: str = "LIVE",
        title: Optional[str] = None,
        verification_depth: str = "standard",
        evidence_preference: str = "balanced",
        language: str = "en",
        user_id: Optional[str] = None,
    ) -> InvestigationModel:
        # Default is strictly LIVE; never allow silent downgrade to DEMO
        inv = InvestigationModel(
            user_id=user_id,
            title=title,
            input_mode=input_mode,
            input_type=input_type,
            verification_depth=verification_depth,
            evidence_preference=evidence_preference,
            language=language,
            status="queued",
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return inv

    @staticmethod
    def get_investigation(db: Session, investigation_id: str) -> Optional[InvestigationModel]:
        return db.get(InvestigationModel, investigation_id)

    @staticmethod
    def create_input(
        db: Session,
        investigation_id: str,
        input_type: str,
        original_text: Optional[str] = None,
        url: Optional[str] = None,
        image_storage_ref: Optional[str] = None,
        audio_storage_ref: Optional[str] = None,
        audio_filename: Optional[str] = None,
        audio_mime_type: Optional[str] = None,
        audio_duration: Optional[float] = None,
        content_hash: Optional[str] = None,
        metadata_dict: Optional[Dict[str, Any]] = None,
    ) -> InputModel:
        # For text inputs, compute content hash if not provided
        if not content_hash and original_text:
            content_hash = compute_content_hash(original_text)

        input_record = InputModel(
            investigation_id=investigation_id,
            input_type=input_type,
            original_text=original_text,
            url=url,
            image_storage_reference=image_storage_ref,
            content_hash=content_hash,
            metadata_json=metadata_dict or {},
            # Audio fields (strict Phase 2 rules: transcript is NULL, status is PENDING)
            audio_storage_reference=audio_storage_ref,
            audio_filename=audio_filename,
            audio_mime_type=audio_mime_type,
            audio_duration=audio_duration,
            audio_transcript=None,
            audio_transcription_confidence=None,
            audio_transcription_status="PENDING",
        )
        db.add(input_record)
        db.commit()
        db.refresh(input_record)
        return input_record

    @staticmethod
    def get_inputs_for_investigation(db: Session, investigation_id: str) -> List[InputModel]:
        stmt = select(InputModel).where(InputModel.investigation_id == investigation_id)
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_claim(
        db: Session,
        investigation_id: str,
        claim_text: str,
        claim_type: Optional[str] = None,
        context: Optional[str] = None,
        order_index: int = 0,
        extraction_confidence: Optional[float] = None,
    ) -> ClaimModel:
        claim = ClaimModel(
            investigation_id=investigation_id,
            claim_text=claim_text,
            claim_type=claim_type,
            context=context,
            order_index=order_index,
            extraction_confidence=extraction_confidence,
            status="extracted",
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)
        return claim

    @staticmethod
    def get_claims_for_investigation(db: Session, investigation_id: str) -> List[ClaimModel]:
        stmt = (
            select(ClaimModel)
            .where(ClaimModel.investigation_id == investigation_id)
            .order_by(ClaimModel.order_index.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_claim_task(
        db: Session,
        claim_id: str,
        task_description: str,
        search_query: Optional[str] = None,
    ) -> ClaimTaskModel:
        task = ClaimTaskModel(
            claim_id=claim_id,
            task_description=task_description,
            search_query=search_query,
            task_status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def get_or_create_source(
        db: Session,
        url: str,
        title: Optional[str] = None,
        publisher: Optional[str] = None,
        domain: Optional[str] = None,
        publication_date: Optional[datetime] = None,
    ) -> SourceModel:
        stmt = select(SourceModel).where(SourceModel.url == url)
        existing = db.scalars(stmt).first()
        if existing:
            return existing

        source = SourceModel(
            url=url,
            title=title,
            publisher=publisher,
            domain=domain,
            publication_date=publication_date,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def add_evidence(
        db: Session,
        claim_id: str,
        source_id: str,
        exact_relevant_excerpt: str,
        relationship: str = "SUPPORTING",
        relevance: Optional[float] = None,
    ) -> EvidenceModel:
        evidence = EvidenceModel(
            claim_id=claim_id,
            source_id=source_id,
            exact_relevant_excerpt=exact_relevant_excerpt,
            relationship_type=relationship,
            relevance=relevance,
        )
        db.add(evidence)
        db.flush()

        # Link junction table
        junction = ClaimEvidenceModel(
            claim_id=claim_id,
            evidence_id=evidence.id,
            relationship_type=relationship,
            relevance_score=relevance,
        )
        db.add(junction)
        db.commit()
        db.refresh(evidence)
        return evidence

    @staticmethod
    def get_evidence_for_investigation(db: Session, investigation_id: str) -> List[EvidenceModel]:
        """Retrieves evidence strictly scoped to claims belonging to this investigation."""
        stmt = (
            select(EvidenceModel)
            .join(ClaimModel, EvidenceModel.claim_id == ClaimModel.id)
            .where(ClaimModel.investigation_id == investigation_id)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_verification_result(
        db: Session,
        investigation_id: str,
        verdict: str,
        claim_id: Optional[str] = None,
        model_confidence: Optional[float] = None,
        confidence: Optional[float] = None,
        evidence_sufficiency: Optional[str] = None,
        supporting_count: int = 0,
        contradicting_count: int = 0,
        inconclusive_count: int = 0,
        explanation: Optional[str] = None,
    ) -> VerificationResultModel:
        eff_conf = confidence if confidence is not None else model_confidence
        res = VerificationResultModel(
            investigation_id=investigation_id,
            claim_id=claim_id,
            verdict=verdict,
            model_confidence=eff_conf,
            evidence_sufficiency=evidence_sufficiency,
            supporting_count=supporting_count,
            contradicting_count=contradicting_count,
            inconclusive_count=inconclusive_count,
            explanation=explanation,
        )
        db.add(res)
        db.commit()
        db.refresh(res)
        return res

    @staticmethod
    def add_timeline_event(
        db: Session,
        investigation_id: str,
        event_type: str,
        description: str,
        event_date: Optional[datetime] = None,
        claim_id: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> TimelineEventModel:
        evt = TimelineEventModel(
            investigation_id=investigation_id,
            claim_id=claim_id,
            event_type=event_type,
            event_date=event_date or now_utc(),
            source_reference=source_reference,
            description=description,
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        return evt

    @staticmethod
    def add_agent_event(
        db: Session,
        investigation_id: str,
        event_type: str,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        metadata_dict: Optional[Dict[str, Any]] = None,
    ) -> AgentEventModel:
        evt = AgentEventModel(
            investigation_id=investigation_id,
            event_type=event_type,
            stage=stage,
            message=message,
            metadata_json=metadata_dict or {},
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        return evt

    @staticmethod
    def add_copilot_message(
        db: Session,
        investigation_id: str,
        role: str,
        message: str,
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> CopilotMessageModel:
        msg = CopilotMessageModel(
            investigation_id=investigation_id,
            role=role,
            message=message,
            citations=citations or [],
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def delete_investigation(db: Session, investigation_id: str) -> bool:
        """
        Safely deletes investigation and cascades to all child records
        (inputs, claims, tasks, evidence relationships, results, timeline, agent events, copilot)
        without deleting shared source records.
        """
        inv = db.get(InvestigationModel, investigation_id)
        if not inv:
            return False
        db.delete(inv)
        db.commit()
        return True


repo = InvestigationRepository()
