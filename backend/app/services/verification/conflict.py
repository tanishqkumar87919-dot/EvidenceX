from typing import Any, Dict, List, Set
from .base import EvidenceInput


class ConflictAnalyzer:
    """
    Analyzes evidence consensus and contradiction across sources.
    Identifies conflicting claims or sources without masking disagreements.
    """

    @staticmethod
    def analyze_conflict(
        evidence_items: List[EvidenceInput],
        supporting_ids: List[str],
        contradicting_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Builds a structured conflict report mapping evidence items to stances
        and highlighting conflicts between independent sources.
        """
        supp_set: Set[str] = set(supporting_ids)
        cont_set: Set[str] = set(contradicting_ids)

        supporting_sources: List[Dict[str, str]] = []
        contradicting_sources: List[Dict[str, str]] = []
        inconclusive_sources: List[Dict[str, str]] = []

        for e in evidence_items:
            info = {
                "evidence_id": e.evidence_id,
                "url": e.source_url,
                "domain": e.domain or e.publisher or "unknown",
                "publisher": e.publisher or "unknown",
                "excerpt": e.exact_excerpt[:160],
            }
            if e.evidence_id in supp_set:
                supporting_sources.append(info)
            elif e.evidence_id in cont_set:
                contradicting_sources.append(info)
            else:
                inconclusive_sources.append(info)

        has_conflict = len(supporting_sources) > 0 and len(contradicting_sources) > 0

        conflict_summary = None
        if has_conflict:
            supp_domains = list(set(s["domain"] for s in supporting_sources))
            cont_domains = list(set(s["domain"] for s in contradicting_sources))
            conflict_summary = (
                f"Conflicting evidence detected between supporting sources ({', '.join(supp_domains[:2])}) "
                f"and contradicting sources ({', '.join(cont_domains[:2])})."
            )

        return {
            "has_conflict": has_conflict,
            "supporting_count": len(supporting_sources),
            "contradicting_count": len(contradicting_sources),
            "inconclusive_count": len(inconclusive_sources),
            "supporting_sources": supporting_sources,
            "contradicting_sources": contradicting_sources,
            "inconclusive_sources": inconclusive_sources,
            "conflict_summary": conflict_summary,
        }


conflict_analyzer = ConflictAnalyzer()
