from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import ClaimExtractionException
from ...database.models import ClaimModel, ClaimTaskModel
from ...database.repository import InvestigationRepository
from ...schemas.claim import ClaimStatus, ExtractedClaimCandidate
from ...schemas.ingest import NormalizedInput
from ..llm import get_llm_provider


class ClaimExtractionService:
    """
    Core Phase 4 Agentic Claim Extraction and Decomposition Orchestrator.
    Processes normalized content across all modalities (TEXT, IMAGE, URL, AUDIO),
    invokes the active LLM provider, decomposes compound statements into atomic units,
    generates targeted verification tasks, and persists everything transactionally to PostgreSQL / SQLite.
    """

    async def extract_from_text(
        self,
        text: str,
        investigation_id: str,
        language: str = "en",
    ) -> List[ExtractedClaimCandidate]:
        """
        Runs claim extraction and decomposition on raw or normalized text using
        the active LLM/NLP provider.
        """
        if not text or not text.strip():
            return []

        provider = get_llm_provider()
        return await provider.extract_and_decompose_claims(
            text=text,
            investigation_id=investigation_id,
            language=language,
        )

    async def extract_and_persist(
        self,
        db: Session,
        investigation_id: str,
        normalized: Optional[NormalizedInput] = None,
        raw_text: Optional[str] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Extracts atomic claims and tasks from normalized input or raw text,
        then persists the full relational graph into the database.
        """
        # Determine source text and language
        text_to_process = ""
        effective_lang = language

        if normalized:
            effective_lang = normalized.language if normalized.language != "UNKNOWN" else language
            input_type_str = normalized.input_type.value if hasattr(normalized.input_type, "value") else str(normalized.input_type)
            if input_type_str == "AUDIO":
                text_to_process = normalized.audio_transcript or ""
            else:
                text_to_process = normalized.text or ""
        elif raw_text:
            text_to_process = raw_text

        text_to_process = text_to_process.strip()

        if not text_to_process:
            # No verifiable text content in input
            InvestigationRepository.update_investigation_status(db, investigation_id, "ready_for_retrieval")
            return {
                "investigation_id": investigation_id,
                "claims_count": 0,
                "tasks_count": 0,
                "status": "ready_for_retrieval",
                "claims": [],
            }

        # Run extraction & decomposition
        candidates = await self.extract_from_text(
            text=text_to_process,
            investigation_id=investigation_id,
            language=effective_lang,
        )

        persisted_claims: List[ClaimModel] = []
        total_tasks_count = 0

        # Persist claims and verification tasks
        for idx, candidate in enumerate(candidates):
            claim_type_str = (
                candidate.claim_type.value
                if hasattr(candidate.claim_type, "value")
                else str(candidate.claim_type)
            )

            claim_record = InvestigationRepository.create_claim(
                db=db,
                investigation_id=investigation_id,
                claim_text=candidate.claim_text,
                claim_type=claim_type_str,
                context=candidate.context,
                order_index=idx,
                extraction_confidence=candidate.extraction_confidence,
            )

            # Update status to TASKS_CREATED
            InvestigationRepository.update_claim_status(
                db=db,
                claim_id=claim_record.id,
                status=ClaimStatus.TASKS_CREATED.value.lower(),
            )

            # Persist tasks for this atomic claim
            for task_plan in candidate.verification_tasks:
                task_record = InvestigationRepository.create_claim_task(
                    db=db,
                    claim_id=claim_record.id,
                    task_description=task_plan.task_description,
                    search_query=task_plan.search_query,
                )
                total_tasks_count += 1

            persisted_claims.append(claim_record)

        # Record Investigation Timeline Events
        if persisted_claims:
            InvestigationRepository.add_timeline_event(
                db=db,
                investigation_id=investigation_id,
                event_type="claims_extracted",
                description=f"Extracted {len(persisted_claims)} verifiable claims from input.",
            )
            if total_tasks_count > 0:
                InvestigationRepository.add_timeline_event(
                    db=db,
                    investigation_id=investigation_id,
                    event_type="tasks_generated",
                    description=f"Generated {total_tasks_count} verification queries and tasks.",
                )

        # Record Agent Event for Orchestration Observability
        InvestigationRepository.add_agent_event(
            db=db,
            investigation_id=investigation_id,
            event_type="CLAIM_EXTRACTION",
            stage="CLAIM_EXTRACTION",
            message=f"Claim extraction completed. Identified {len(persisted_claims)} claims and {total_tasks_count} tasks.",
            metadata_dict={
                "claims_count": len(persisted_claims),
                "tasks_count": total_tasks_count,
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
            },
        )

        # Update Investigation Status
        InvestigationRepository.update_investigation_status(
            db=db,
            investigation_id=investigation_id,
            status="tasks_created",
        )

        return {
            "investigation_id": investigation_id,
            "claims_count": len(persisted_claims),
            "tasks_count": total_tasks_count,
            "status": "tasks_created",
            "claims": persisted_claims,
        }


claim_extraction_service = ClaimExtractionService()
