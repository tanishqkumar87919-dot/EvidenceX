from typing import List, Set
from .base import (
    BaseVerificationProvider,
    ClaimVerificationInput,
    VerificationOutput,
)
from .evaluator import evidence_sufficiency_evaluator


class DeterministicVerificationProvider(BaseVerificationProvider):
    """
    Deterministic rule- and stance-based verification provider for offline testing
    and deterministic verification suites without external network/API dependencies.
    """

    def __init__(self, model_name: str = "deterministic-rule-v1"):
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def verify_claim(
        self,
        claim_input: ClaimVerificationInput,
    ) -> VerificationOutput:
        sufficiency, strength, temporal_notes = evidence_sufficiency_evaluator.evaluate(
            claim_text=claim_input.claim_text,
            evidence_items=claim_input.evidence_items,
        )

        if not claim_input.evidence_items:
            return VerificationOutput(
                verdict="INSUFFICIENT_EVIDENCE",
                confidence=0.95,
                evidence_sufficiency="INSUFFICIENT",
                evidence_strength=0.0,
                explanation="No verifiable evidence could be retrieved from external sources for this claim.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                uncertainty="Lack of external web sources addressing this assertion.",
                model_provider=f"{self.provider_name}:{self.model_name}",
            )

        supporting_ids: List[str] = []
        contradicting_ids: List[str] = []
        inconclusive_ids: List[str] = []

        claim_lower = claim_input.claim_text.lower()
        negation_cues = {"not", "never", "false", "disputed", "hoax", "debunked", "incorrect", "denied", "no evidence"}

        for ev in claim_input.evidence_items:
            excerpt_lower = ev.exact_excerpt.lower()
            stance = ev.preliminary_stance.upper() if ev.preliminary_stance else "INCONCLUSIVE"

            has_negation = any(cue in excerpt_lower for cue in negation_cues)
            if stance == "CONTRADICTING" or (has_negation and stance != "SUPPORTING"):
                contradicting_ids.append(ev.evidence_id)
            elif stance == "SUPPORTING":
                supporting_ids.append(ev.evidence_id)
            else:
                inconclusive_ids.append(ev.evidence_id)

        # Decide verdict based on counts and strength
        supp_count = len(supporting_ids)
        cont_count = len(contradicting_ids)

        if supp_count > 0 and cont_count == 0:
            verdict = "SUPPORTED"
            confidence = min(0.95, 0.70 + 0.10 * supp_count)
            explanation = f"Evaluated against {len(claim_input.evidence_items)} external source passages. The assertion is corroborated across {supp_count} supporting sources."
            uncertainty = temporal_notes
        elif cont_count > 0 and supp_count == 0:
            verdict = "CONTRADICTED"
            confidence = min(0.95, 0.70 + 0.10 * cont_count)
            explanation = f"Evaluated against {len(claim_input.evidence_items)} external source passages. The assertion is contradicted by {cont_count} sources."
            uncertainty = temporal_notes
        elif supp_count > 0 and cont_count > 0:
            verdict = "PARTIALLY_SUPPORTED"
            confidence = 0.65
            explanation = f"Conflicting evidence detected: {supp_count} supporting vs {cont_count} contradicting passages across external sources."
            uncertainty = "Source conflict detected between opposing reports."
        elif sufficiency == "INSUFFICIENT" or strength < 0.25:
            verdict = "INSUFFICIENT_EVIDENCE"
            confidence = 0.80
            explanation = "The retrieved passages lack sufficient direct relevance to decisively confirm or refute the claim."
            uncertainty = "Sparse or low-relevance evidence passages."
        else:
            verdict = "INCONCLUSIVE"
            confidence = 0.50
            explanation = "Retrieved evidence does not provide decisive factual confirmation in either direction."
            uncertainty = "Ambiguous or neutral source statements."

        return VerificationOutput(
            verdict=verdict,
            confidence=round(confidence, 4),
            evidence_sufficiency=sufficiency,
            evidence_strength=strength,
            explanation=explanation,
            supporting_evidence_ids=supporting_ids,
            contradicting_evidence_ids=contradicting_ids,
            uncertainty=uncertainty,
            model_provider=f"{self.provider_name}:{self.model_name}",
        )
