from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ...core.errors import NotFoundException
from ...database.models import ClaimModel, EvidenceModel, InvestigationModel, VerificationResultModel
from ...database.repository import InvestigationRepository
from ...schemas.results import (
    ClaimResultItem,
    EvidenceReferenceItem,
    InvestigationResultsResponse,
    ResultSummary,
)


def _get_source_quality(authority_score: Optional[float]) -> str:
    if authority_score is None:
        return "MEDIUM"
    if authority_score >= 0.80:
        return "HIGH"
    if authority_score >= 0.50:
        return "MEDIUM"
    return "LOW"


class ResultsService:
    """
    Transforms persisted claim verification results and evidence graphs into
    the structured, explainable results representation powering the frontend.
    """

    @staticmethod
    def get_investigation_results(
        db: Session,
        investigation_id: str,
        request_id: str = "",
    ) -> InvestigationResultsResponse:
        inv = InvestigationRepository.get_investigation(db, investigation_id)
        if not inv:
            raise NotFoundException(
                message=f"Investigation '{investigation_id}' not found.",
                details={"investigation_id": investigation_id},
            )

        claims = InvestigationRepository.get_claims_for_investigation(db, investigation_id)
        claim_results: List[ClaimResultItem] = []

        supported_cnt = 0
        contradicted_cnt = 0
        partially_supported_cnt = 0
        inconclusive_cnt = 0
        insufficient_cnt = 0
        conf_sum = 0.0
        conf_count = 0

        all_supporting_ids = set()
        all_contradicting_ids = set()
        all_source_ids = set()

        for claim in claims:
            vr = InvestigationRepository.get_verification_result_for_claim(db, claim.id)
            ev_list = InvestigationRepository.get_evidence_for_claim(db, claim.id)

            ev_by_id: Dict[str, EvidenceModel] = {str(ev.id): ev for ev in ev_list}
            for ev in ev_list:
                if ev.source_id:
                    all_source_ids.add(str(ev.source_id))

            supp_refs: List[EvidenceReferenceItem] = []
            cont_refs: List[EvidenceReferenceItem] = []

            supp_ids_target = set(vr.supporting_evidence_ids if vr and vr.supporting_evidence_ids else [])
            cont_ids_target = set(vr.contradicting_evidence_ids if vr and vr.contradicting_evidence_ids else [])

            for ev in ev_list:
                ev_id_str = str(ev.id)
                src = ev.source
                ref_item = EvidenceReferenceItem(
                    evidence_id=ev_id_str,
                    excerpt=ev.exact_relevant_excerpt,
                    source_title=src.title if src and src.title else (src.url if src else "External Source"),
                    source_url=src.url if src else "",
                    domain=src.domain if src else None,
                    source_category=src.source_type if src else None,
                    source_quality=_get_source_quality(float(ev.relevance) if ev.relevance is not None else None),
                    relevance_score=float(ev.relevance) if ev.relevance is not None else None,
                    publication_date=src.publication_date.isoformat() if src and src.publication_date else None,
                    stance=(ev.relationship_type or "SUPPORTING").lower(),
                )

                if ev_id_str in supp_ids_target:
                    ref_item.stance = "supporting"
                    supp_refs.append(ref_item)
                    all_supporting_ids.add(ev_id_str)
                elif ev_id_str in cont_ids_target:
                    ref_item.stance = "contradicting"
                    cont_refs.append(ref_item)
                    all_contradicting_ids.add(ev_id_str)
                elif ev.relationship_type == "SUPPORTING" and vr and vr.verdict in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                    ref_item.stance = "supporting"
                    supp_refs.append(ref_item)
                    all_supporting_ids.add(ev_id_str)
                elif ev.relationship_type == "CONTRADICTING" and vr and vr.verdict in ("CONTRADICTED", "PARTIALLY_SUPPORTED"):
                    ref_item.stance = "contradicting"
                    cont_refs.append(ref_item)
                    all_contradicting_ids.add(ev_id_str)

            verdict = vr.verdict if vr else "INSUFFICIENT_EVIDENCE"
            v_upper = verdict.upper()
            if v_upper == "SUPPORTED":
                supported_cnt += 1
            elif v_upper in ("CONTRADICTED", "REFUTED"):
                contradicted_cnt += 1
            elif v_upper == "PARTIALLY_SUPPORTED":
                partially_supported_cnt += 1
            elif v_upper == "INCONCLUSIVE":
                inconclusive_cnt += 1
            elif v_upper == "INSUFFICIENT_EVIDENCE":
                insufficient_cnt += 1

            conf = float(vr.model_confidence) if vr and vr.model_confidence is not None else 0.50
            conf_sum += conf
            conf_count += 1

            strength = float(vr.evidence_strength) if vr and vr.evidence_strength is not None else 0.50
            sufficiency = vr.evidence_sufficiency if vr and vr.evidence_sufficiency else "MEDIUM"
            reason = vr.explanation if vr and vr.explanation else "Verification pending or insufficient evidence."
            uncertainty = vr.uncertainty if vr else None

            claim_results.append(
                ClaimResultItem(
                    claim_id=str(claim.id),
                    claim_text=claim.claim_text,
                    claim_type=claim.claim_type or "OTHER",
                    verdict=verdict,
                    confidence=round(conf, 4),
                    evidence_sufficiency=sufficiency,
                    evidence_strength=round(strength, 4),
                    reason=reason,
                    supporting_evidence=supp_refs,
                    contradicting_evidence=cont_refs,
                    uncertainty=uncertainty,
                )
            )

        total_claims = len(claims)
        avg_confidence = round(conf_sum / conf_count, 4) if conf_count > 0 else 0.0

        # Determine overall verdict
        if total_claims == 0:
            overall_verdict = "INCONCLUSIVE"
        elif supported_cnt == total_claims:
            overall_verdict = "SUPPORTED"
        elif contradicted_cnt == total_claims:
            overall_verdict = "CONTRADICTED"
        elif supported_cnt > 0 and contradicted_cnt == 0:
            overall_verdict = "MOSTLY_SUPPORTED"
        elif contradicted_cnt > 0 and supported_cnt > 0:
            overall_verdict = "MIXED"
        elif partially_supported_cnt > 0:
            overall_verdict = "PARTIALLY_SUPPORTED"
        elif insufficient_cnt == total_claims:
            overall_verdict = "INSUFFICIENT_EVIDENCE"
        else:
            overall_verdict = "INCONCLUSIVE"

        summary = ResultSummary(
            total_claims=total_claims,
            supported=supported_cnt,
            contradicted=contradicted_cnt,
            partially_supported=partially_supported_cnt,
            inconclusive=inconclusive_cnt,
            insufficient_evidence=insufficient_cnt,
            average_confidence=avg_confidence,
            overall_verdict=overall_verdict,
            supporting_evidence_count=len(all_supporting_ids),
            contradicting_evidence_count=len(all_contradicting_ids),
            source_count=len(all_source_ids),
        )

        verified_claims_cnt = supported_cnt + contradicted_cnt + partially_supported_cnt + inconclusive_cnt
        return InvestigationResultsResponse(
            investigation_id=str(inv.id),
            status=inv.status.upper(),
            total_claims=len(claims),
            verified_claims=verified_claims_cnt,
            summary=summary,
            claims=claim_results,
            overall_verdict=overall_verdict,
            average_confidence=avg_confidence,
            created_at=inv.created_at.isoformat() if inv.created_at else None,
            request_id=request_id,
        )


results_service = ResultsService()
