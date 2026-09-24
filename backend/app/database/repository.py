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
    EvidenceChunkModel,
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
        extracted_text: Optional[str] = None,
        audio_transcript: Optional[str] = None,
        audio_transcription_confidence: Optional[float] = None,
        audio_transcription_status: Optional[str] = None,
    ) -> InputModel:
        # For text inputs, compute content hash if not provided
        if not content_hash and original_text:
            content_hash = compute_content_hash(original_text)
        elif not content_hash and extracted_text:
            content_hash = compute_content_hash(extracted_text)

        # Default transcription status
        status = audio_transcription_status
        if status is None:
            status = "COMPLETED" if audio_transcript is not None else "PENDING"

        input_record = InputModel(
            investigation_id=investigation_id,
            input_type=input_type,
            original_text=original_text,
            url=url,
            image_storage_reference=image_storage_ref,
            extracted_text=extracted_text,
            content_hash=content_hash,
            metadata_json=metadata_dict or {},
            # Audio fields (Phase 2 & Phase 3 real STT)
            audio_storage_reference=audio_storage_ref,
            audio_filename=audio_filename,
            audio_mime_type=audio_mime_type,
            audio_duration=audio_duration,
            audio_transcript=audio_transcript,
            audio_transcription_confidence=audio_transcription_confidence,
            audio_transcription_status=status,
        )
        db.add(input_record)
        db.commit()
        db.refresh(input_record)
        return input_record

    @staticmethod
    def persist_normalized_input(
        db: Session,
        normalized: Any,
        title: Optional[str] = None,
        verification_depth: str = "standard",
        evidence_preference: str = "balanced",
        user_id: Optional[str] = None,
    ) -> tuple:
        """
        Atomically persists a NormalizedInput into the database:
        Creates/updates investigation and attaches input record.
        """
        inv_id = normalized.investigation_id
        inv = db.get(InvestigationModel, inv_id)
        if not inv:
            inv = InvestigationModel(
                id=inv_id,
                user_id=user_id,
                title=title or (normalized.text[:50] + "..." if normalized.text else f"{normalized.input_type} investigation"),
                input_mode=normalized.input_mode.value if hasattr(normalized.input_mode, "value") else str(normalized.input_mode),
                input_type=normalized.input_type.value if hasattr(normalized.input_type, "value") else str(normalized.input_type),
                status="received",
                language=normalized.language if normalized.language != "UNKNOWN" else "en",
                verification_depth=verification_depth,
                evidence_preference=evidence_preference,
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)

        input_type_str = normalized.input_type.value if hasattr(normalized.input_type, "value") else str(normalized.input_type)
        input_record = InvestigationRepository.create_input(
            db=db,
            investigation_id=inv.id,
            input_type=input_type_str,
            original_text=normalized.text if input_type_str == "TEXT" else None,
            url=normalized.url,
            image_storage_ref=normalized.image_reference,
            audio_storage_ref=normalized.audio_reference,
            audio_filename=normalized.metadata.get("audio_filename"),
            audio_mime_type=normalized.metadata.get("audio_mime_type"),
            audio_duration=normalized.metadata.get("audio_duration"),
            content_hash=normalized.content_hash,
            metadata_dict=normalized.metadata,
            extracted_text=normalized.text if input_type_str in ("IMAGE", "URL") else None,
            audio_transcript=normalized.audio_transcript,
            audio_transcription_confidence=normalized.audio_transcription_confidence,
            audio_transcription_status="COMPLETED" if normalized.audio_transcript else ("FAILED" if normalized.metadata.get("transcription_failed") else "PENDING"),
        )
        return inv, input_record

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
    def get_claim(db: Session, claim_id: str) -> Optional[ClaimModel]:
        return db.get(ClaimModel, claim_id)

    @staticmethod
    def get_claim_tasks_for_claim(db: Session, claim_id: str) -> List[ClaimTaskModel]:
        stmt = (
            select(ClaimTaskModel)
            .where(ClaimTaskModel.claim_id == claim_id)
            .order_by(ClaimTaskModel.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_all_tasks_for_investigation(db: Session, investigation_id: str) -> List[ClaimTaskModel]:
        stmt = (
            select(ClaimTaskModel)
            .join(ClaimModel, ClaimTaskModel.claim_id == ClaimModel.id)
            .where(ClaimModel.investigation_id == investigation_id)
            .order_by(ClaimTaskModel.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_investigation_status(
        db: Session,
        investigation_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[InvestigationModel]:
        inv = db.get(InvestigationModel, investigation_id)
        if inv:
            inv.status = status
            if error_message is not None:
                inv.error_message = error_message
            db.commit()
            db.refresh(inv)
        return inv

    @staticmethod
    def update_claim_status(
        db: Session,
        claim_id: str,
        status: str,
    ) -> Optional[ClaimModel]:
        claim = db.get(ClaimModel, claim_id)
        if claim:
            claim.status = status
            db.commit()
            db.refresh(claim)
        return claim

    @staticmethod
    def get_or_create_source(
        db: Session,
        url: str,
        title: Optional[str] = None,
        publisher: Optional[str] = None,
        domain: Optional[str] = None,
        publication_date: Optional[datetime] = None,
        author: Optional[str] = None,
        source_type: Optional[str] = None,
        canonical_url: Optional[str] = None,
    ) -> SourceModel:
        stmt = select(SourceModel).where(SourceModel.url == url)
        existing = db.scalars(stmt).first()
        if existing:
            updated = False
            if title and not existing.title:
                existing.title = title
                updated = True
            if publisher and not existing.publisher:
                existing.publisher = publisher
                updated = True
            if author and not existing.author:
                existing.author = author
                updated = True
            if source_type and not existing.source_type:
                existing.source_type = source_type
                updated = True
            if canonical_url and not existing.canonical_url:
                existing.canonical_url = canonical_url
                updated = True
            if publication_date and not existing.publication_date:
                existing.publication_date = publication_date
                updated = True
            if updated:
                db.commit()
                db.refresh(existing)
            return existing

        source = SourceModel(
            url=url,
            title=title,
            publisher=publisher,
            domain=domain,
            publication_date=publication_date,
            author=author,
            source_type=source_type,
            canonical_url=canonical_url,
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
        source_assessment: Optional[Dict[str, Any]] = None,
        temporal_information: Optional[Dict[str, Any]] = None,
    ) -> EvidenceModel:
        evidence = EvidenceModel(
            claim_id=claim_id,
            source_id=source_id,
            exact_relevant_excerpt=exact_relevant_excerpt,
            relationship_type=relationship,
            relevance=relevance,
            source_assessment=source_assessment or {},
            temporal_information=temporal_information or {},
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
    def create_evidence_chunk(
        db: Session,
        investigation_id: str,
        source_id: str,
        content: str,
        chunk_index: int = 0,
        claim_id: Optional[str] = None,
        heading: Optional[str] = None,
        character_count: int = 0,
        token_count: Optional[int] = None,
        embedding: Optional[List[float]] = None,
        embedding_model: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> EvidenceChunkModel:
        chunk = EvidenceChunkModel(
            investigation_id=investigation_id,
            claim_id=claim_id,
            source_id=source_id,
            chunk_index=chunk_index,
            content=content,
            heading=heading,
            character_count=character_count or len(content),
            token_count=token_count or len(content.split()),
            embedding=embedding,
            embedding_model=embedding_model,
            metadata_json=metadata_json or {},
        )
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        return chunk

    @staticmethod
    def get_evidence_chunks_for_investigation(
        db: Session, investigation_id: str
    ) -> List[EvidenceChunkModel]:
        stmt = (
            select(EvidenceChunkModel)
            .where(EvidenceChunkModel.investigation_id == investigation_id)
            .order_by(EvidenceChunkModel.chunk_index.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_evidence_chunks_for_claim(
        db: Session, claim_id: str
    ) -> List[EvidenceChunkModel]:
        stmt = (
            select(EvidenceChunkModel)
            .where(EvidenceChunkModel.claim_id == claim_id)
            .order_by(EvidenceChunkModel.chunk_index.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_evidence_by_id(db: Session, evidence_id: str) -> Optional[EvidenceModel]:
        return db.get(EvidenceModel, evidence_id)

    @staticmethod
    def get_evidence_for_claim(db: Session, claim_id: str) -> List[EvidenceModel]:
        stmt = (
            select(EvidenceModel)
            .where(EvidenceModel.claim_id == claim_id)
            .order_by(EvidenceModel.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_sources_for_investigation(db: Session, investigation_id: str) -> List[SourceModel]:
        """Returns all distinct sources referenced by evidence or evidence_chunks for this investigation."""
        stmt = (
            select(SourceModel)
            .join(EvidenceModel, EvidenceModel.source_id == SourceModel.id)
            .join(ClaimModel, EvidenceModel.claim_id == ClaimModel.id)
            .where(ClaimModel.investigation_id == investigation_id)
            .distinct()
        )
        sources = list(db.scalars(stmt).all())
        if not sources:
            stmt2 = (
                select(SourceModel)
                .join(EvidenceChunkModel, EvidenceChunkModel.source_id == SourceModel.id)
                .where(EvidenceChunkModel.investigation_id == investigation_id)
                .distinct()
            )
            sources = list(db.scalars(stmt2).all())
        return sources

    @staticmethod
    def update_claim_task_status(
        db: Session,
        task_id: str,
        status: str = "completed",
    ) -> Optional[ClaimTaskModel]:
        task = db.get(ClaimTaskModel, task_id)
        if task:
            task.task_status = status
            if status == "completed":
                task.completion_time = now_utc()
            db.commit()
            db.refresh(task)
        return task

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
    def create_or_update_verification_result(
        db: Session,
        investigation_id: str,
        verdict: str,
        claim_id: Optional[str] = None,
        model_confidence: Optional[float] = None,
        evidence_sufficiency: Optional[str] = None,
        evidence_strength: Optional[float] = None,
        supporting_count: int = 0,
        contradicting_count: int = 0,
        inconclusive_count: int = 0,
        supporting_evidence_ids: Optional[List[str]] = None,
        contradicting_evidence_ids: Optional[List[str]] = None,
        explanation: Optional[str] = None,
        uncertainty: Optional[str] = None,
        model_provider: Optional[str] = None,
    ) -> VerificationResultModel:
        """
        Creates or updates a claim verification result in Supabase PostgreSQL.
        Guarantees that each claim has a single canonical verification result.
        """
        existing = None
        if claim_id:
            stmt = select(VerificationResultModel).where(VerificationResultModel.claim_id == claim_id)
            existing = db.scalars(stmt).first()

        if existing:
            existing.verdict = verdict
            existing.model_confidence = model_confidence
            existing.evidence_sufficiency = evidence_sufficiency
            existing.evidence_strength = evidence_strength
            existing.supporting_count = supporting_count
            existing.contradicting_count = contradicting_count
            existing.inconclusive_count = inconclusive_count
            existing.supporting_evidence_ids = supporting_evidence_ids or []
            existing.contradicting_evidence_ids = contradicting_evidence_ids or []
            existing.explanation = explanation
            existing.uncertainty = uncertainty
            existing.model_provider = model_provider
            existing.updated_at = now_utc()
            db.commit()
            db.refresh(existing)
            return existing

        res = VerificationResultModel(
            investigation_id=investigation_id,
            claim_id=claim_id,
            verdict=verdict,
            model_confidence=model_confidence,
            evidence_sufficiency=evidence_sufficiency,
            evidence_strength=evidence_strength,
            supporting_count=supporting_count,
            contradicting_count=contradicting_count,
            inconclusive_count=inconclusive_count,
            supporting_evidence_ids=supporting_evidence_ids or [],
            contradicting_evidence_ids=contradicting_evidence_ids or [],
            explanation=explanation,
            uncertainty=uncertainty,
            model_provider=model_provider,
        )
        db.add(res)
        db.commit()
        db.refresh(res)
        return res

    @staticmethod
    def get_verification_results_for_investigation(
        db: Session, investigation_id: str
    ) -> List[VerificationResultModel]:
        stmt = (
            select(VerificationResultModel)
            .where(VerificationResultModel.investigation_id == investigation_id)
            .order_by(VerificationResultModel.generated_timestamp.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_verification_result_for_claim(
        db: Session, claim_id: str
    ) -> Optional[VerificationResultModel]:
        stmt = select(VerificationResultModel).where(VerificationResultModel.claim_id == claim_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_verification_result_by_id(
        db: Session, result_id: str
    ) -> Optional[VerificationResultModel]:
        return db.get(VerificationResultModel, result_id)

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
