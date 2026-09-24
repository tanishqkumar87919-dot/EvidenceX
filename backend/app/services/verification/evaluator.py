import re
from typing import List, Optional, Tuple
from .base import EvidenceInput


class EvidenceSufficiencyEvaluator:
    """
    Evaluates evidence sufficiency and strength based on multi-factor analysis:
    - Number of distinct sources/domains
    - Authority & credibility weights
    - Semantic & lexical relevance scores
    - Directness and consistency
    - Temporal context detection
    """

    @staticmethod
    def evaluate(
        claim_text: str,
        evidence_items: List[EvidenceInput],
    ) -> Tuple[str, float, Optional[str]]:
        """
        Returns:
            (sufficiency_level, evidence_strength, temporal_notes)
            sufficiency_level: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT"
            evidence_strength: float in [0.0, 1.0]
            temporal_notes: optional string describing temporal observations
        """
        if not evidence_items:
            return "INSUFFICIENT", 0.0, "No evidence items available for this claim."

        # 1. Distinct domains for independence
        distinct_domains = set(e.domain for e in evidence_items if e.domain)
        distinct_sources = len(distinct_domains) if distinct_domains else len(evidence_items)

        # 2. Weighted credibility and relevance
        credibility_scores = [e.credibility_weight for e in evidence_items]
        relevance_scores = [e.relevance_score if e.relevance_score is not None else 0.5 for e in evidence_items]

        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0.5
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5

        # 3. Temporal analysis: check if claim specifies a year and if evidence contains publication dates
        temporal_notes = None
        claim_years = re.findall(r"\b(19\d{2}|20\d{2})\b", claim_text)
        evidence_dates = [e.publication_date for e in evidence_items if e.publication_date]
        if claim_years and evidence_dates:
            target_year = claim_years[0]
            # Check if any evidence explicitly discusses the target year
            matches_year = any(target_year in e.exact_excerpt for e in evidence_items)
            if not matches_year:
                temporal_notes = (
                    f"Claim mentions year {target_year}; sources were published at various dates "
                    f"({', '.join(evidence_dates[:2])}) and should be inspected for historical event correlation."
                )

        # 4. Strength calculation (normalized score 0.0 - 1.0)
        # Factors: count volume (up to 4 items), domain independence, relevance, credibility
        volume_factor = min(1.0, len(evidence_items) / 3.0)
        diversity_factor = min(1.0, distinct_sources / 2.0)
        raw_strength = (
            0.35 * avg_relevance
            + 0.30 * avg_credibility
            + 0.20 * volume_factor
            + 0.15 * diversity_factor
        )
        evidence_strength = round(min(1.0, max(0.0, raw_strength)), 4)

        # 5. Sufficiency classification
        if len(evidence_items) >= 2 and evidence_strength >= 0.70 and distinct_sources >= 2:
            sufficiency = "HIGH"
        elif len(evidence_items) >= 1 and evidence_strength >= 0.45:
            sufficiency = "MEDIUM"
        elif len(evidence_items) >= 1:
            sufficiency = "LOW"
        else:
            sufficiency = "INSUFFICIENT"

        return sufficiency, evidence_strength, temporal_notes


evidence_sufficiency_evaluator = EvidenceSufficiencyEvaluator()
