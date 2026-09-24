import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from ...core.config import settings
from ...database.models import ClaimModel, InvestigationModel, VerificationResultModel
from ...database.repository import InvestigationRepository
from .base import (
    BaseVerificationProvider,
    ClaimVerificationInput,
    EvidenceInput,
    VerificationOutput,
)
from .conflict import conflict_analyzer
from .factory import get_verification_provider

logger = logging.getLogger(__name__)


class VerificationService:
    """
    Coordinates the full Phase 6 EvidenceX Verification Engine:
    1. Fetches investigation claims and their associated Phase 5 retrieved evidence.
    2. Maps evidence metadata (source authority, publisher, publication date, relevance, preliminary stance).
    3. Executes grounded verification via the active BaseVerificationProvider.
    4. Analyzes source conflict and consensus.
    5. Persists explainable structured verification results in Supabase PostgreSQL.
    6. Manages lifecycle transitions: READY_FOR_VERIFICATION -> VERIFYING -> VERIFIED.
    """

    def __init__(self, provider: Optional[BaseVerificationProvider] = None):
        self._provider = provider

    def get_provider(self) -> BaseVerificationProvider:
        if self._provider is not None:
            return self._provider
        return get_verification_provider()

    async def verify_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> List[VerificationResultModel]:
        """
        Runs claim verification for all claims in an investigation.
        """
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            logger.error(f"Investigation {investigation_id} not found.")
            return []

        # 1. Update investigation status to verifying
        InvestigationRepository.update_investigation_status(db, investigation_id, "verifying")
        InvestigationRepository.add_agent_event(
            db=db,
            investigation_id=investigation_id,
            event_type="VERIFICATION_STARTED",
            stage="verification",
            message="Evidence-grounded verification engine initiated for investigation claims.",
            metadata_dict={"investigation_id": investigation_id},
        )

        claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
        if not claims:
            logger.warning(f"No claims found for investigation {investigation_id}.")
            InvestigationRepository.update_investigation_status(db, investigation_id, "completed")
            return []

        provider = self.get_provider()
        persisted_results: List[VerificationResultModel] = []
        claim_failures: int = 0

        # 2. Verify each claim independently
        for claim in claims:
            try:
                # Update claim status to verifying
                InvestigationRepository.update_claim_status(db, claim.id, "verifying")

                # Fetch associated evidence
                evidence_records = InvestigationRepository.get_evidence_for_claim(db, claim.id)
                evidence_inputs: List[EvidenceInput] = []

                for ev in evidence_records:
                    src = ev.source
                    pub_date = None
                    if src and src.publication_date:
                        pub_date = src.publication_date.isoformat()

                    evidence_inputs.append(
                        EvidenceInput(
                            evidence_id=str(ev.id),
                            exact_excerpt=ev.exact_relevant_excerpt,
                            source_url=src.url if src else "",
                            source_title=src.title if src else None,
                            publisher=src.publisher if src else (src.domain if src else None),
                            domain=src.domain if src else None,
                            source_type=src.source_type if src else None,
                            credibility_weight=0.85 if src and src.source_type in ("OFFICIAL", "GOVERNMENT", "ACADEMIC") else 0.70,
                            publication_date=pub_date,
                            relevance_score=float(ev.relevance) if ev.relevance is not None else 0.75,
                            preliminary_stance=ev.relationship_type or "INCONCLUSIVE",
                        )
                    )

                claim_input = ClaimVerificationInput(
                    investigation_id=investigation_id,
                    claim_id=claim.id,
                    claim_text=claim.claim_text,
                    context=claim.context,
                    claim_type=claim.claim_type,
                    evidence_items=evidence_inputs,
                )

                # Execute verification
                output: VerificationOutput = await provider.verify_claim(claim_input)

                # Conflict and consensus analysis
                conflict_report = conflict_analyzer.analyze_conflict(
                    evidence_items=evidence_inputs,
                    supporting_ids=output.supporting_evidence_ids,
                    contradicting_ids=output.contradicting_evidence_ids,
                )

                # Persist verification result
                result_rec = InvestigationRepository.create_or_update_verification_result(
                    db=db,
                    investigation_id=investigation_id,
                    claim_id=claim.id,
                    verdict=output.verdict,
                    model_confidence=output.confidence,
                    evidence_sufficiency=output.evidence_sufficiency,
                    evidence_strength=output.evidence_strength,
                    supporting_count=conflict_report["supporting_count"],
                    contradicting_count=conflict_report["contradicting_count"],
                    inconclusive_count=conflict_report["inconclusive_count"],
                    supporting_evidence_ids=output.supporting_evidence_ids,
                    contradicting_evidence_ids=output.contradicting_evidence_ids,
                    explanation=output.explanation,
                    uncertainty=output.uncertainty or conflict_report.get("conflict_summary"),
                    model_provider=output.model_provider,
                )
                persisted_results.append(result_rec)

                # Update claim status
                InvestigationRepository.update_claim_status(db, claim.id, "verified")

                InvestigationRepository.add_agent_event(
                    db=db,
                    investigation_id=investigation_id,
                    event_type="CLAIM_VERIFIED",
                    stage="verification",
                    message=f"Claim evaluated with verdict {output.verdict} (Confidence: {output.confidence:.0%}).",
                    metadata_dict={
                        "claim_id": claim.id,
                        "verdict": output.verdict,
                        "confidence": output.confidence,
                        "sufficiency": output.evidence_sufficiency,
                    },
                )

            except Exception as exc:
                logger.error(f"Verification failed for claim {claim.id}: {exc}")
                claim_failures += 1
                InvestigationRepository.update_claim_status(db, claim.id, "failed")
                InvestigationRepository.add_agent_event(
                    db=db,
                    investigation_id=investigation_id,
                    event_type="CLAIM_VERIFICATION_FAILED",
                    stage="verification",
                    message=f"Verification failed for claim: {str(exc)}",
                    metadata_dict={"claim_id": claim.id, "error": str(exc)},
                )

        # 3. Aggregate investigation status
        if claim_failures == 0:
            final_status = "verified"
        elif claim_failures < len(claims):
            final_status = "verification_partial"
        else:
            final_status = "failed"

        InvestigationRepository.update_investigation_status(db, investigation_id, final_status)
        InvestigationRepository.add_agent_event(
            db=db,
            investigation_id=investigation_id,
            event_type="VERIFICATION_COMPLETED",
            stage="verification",
            message=f"Verification concluded with status '{final_status}'. Verified {len(persisted_results)} claims.",
            metadata_dict={
                "status": final_status,
                "verified_claims_count": len(persisted_results),
                "failures_count": claim_failures,
            },
        )

        return persisted_results

    async def verify_single_claim(
        self,
        db: Session,
        claim_id: str,
    ) -> Optional[VerificationResultModel]:
        """
        Verifies a single claim and returns its persisted VerificationResultModel.
        """
        claim = InvestigationRepository.get_claim(db, claim_id)
        if not claim:
            return None

        inv = InvestigationRepository.get_investigation(db, claim.investigation_id)
        provider = self.get_provider()

        evidence_records = InvestigationRepository.get_evidence_for_claim(db, claim.id)
        evidence_inputs: List[EvidenceInput] = []

        for ev in evidence_records:
            src = ev.source
            pub_date = src.publication_date.isoformat() if src and src.publication_date else None
            evidence_inputs.append(
                EvidenceInput(
                    evidence_id=str(ev.id),
                    exact_excerpt=ev.exact_relevant_excerpt,
                    source_url=src.url if src else "",
                    source_title=src.title if src else None,
                    publisher=src.publisher if src else (src.domain if src else None),
                    domain=src.domain if src else None,
                    source_type=src.source_type if src else None,
                    credibility_weight=0.85 if src and src.source_type in ("OFFICIAL", "GOVERNMENT", "ACADEMIC") else 0.70,
                    publication_date=pub_date,
                    relevance_score=float(ev.relevance) if ev.relevance is not None else 0.75,
                    preliminary_stance=ev.relationship_type or "INCONCLUSIVE",
                )
            )

        claim_input = ClaimVerificationInput(
            investigation_id=claim.investigation_id,
            claim_id=claim.id,
            claim_text=claim.claim_text,
            context=claim.context,
            claim_type=claim.claim_type,
            evidence_items=evidence_inputs,
        )

        output = await provider.verify_claim(claim_input)
        conflict_report = conflict_analyzer.analyze_conflict(
            evidence_items=evidence_inputs,
            supporting_ids=output.supporting_evidence_ids,
            contradicting_ids=output.contradicting_evidence_ids,
        )

        result_rec = InvestigationRepository.create_or_update_verification_result(
            db=db,
            investigation_id=claim.investigation_id,
            claim_id=claim.id,
            verdict=output.verdict,
            model_confidence=output.confidence,
            evidence_sufficiency=output.evidence_sufficiency,
            evidence_strength=output.evidence_strength,
            supporting_count=conflict_report["supporting_count"],
            contradicting_count=conflict_report["contradicting_count"],
            inconclusive_count=conflict_report["inconclusive_count"],
            supporting_evidence_ids=output.supporting_evidence_ids,
            contradicting_evidence_ids=output.contradicting_evidence_ids,
            explanation=output.explanation,
            uncertainty=output.uncertainty or conflict_report.get("conflict_summary"),
            model_provider=output.model_provider,
        )
        InvestigationRepository.update_claim_status(db, claim.id, "verified")
        return result_rec


verification_service = VerificationService()
