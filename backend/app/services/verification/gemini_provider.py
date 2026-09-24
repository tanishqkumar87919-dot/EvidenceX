import asyncio
import json
import logging
from typing import List, Optional
import httpx

from ...core.config import settings
from ...core.errors import LLMProviderUnavailableException
from .base import (
    BaseVerificationProvider,
    ClaimVerificationInput,
    VerificationOutput,
)
from .evaluator import evidence_sufficiency_evaluator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the EvidenceX Verification Engine.
Your task is to critically evaluate a factual claim against the supplied retrieved evidence items.

CRITICAL RULES:
1. Use ONLY the supplied evidence items. Do NOT use outside knowledge to introduce facts not present in the excerpts.
2. Do NOT invent evidence, citations, or URLs.
3. Every referenced evidence ID MUST strictly match one of the evidence IDs provided in the input.
4. Distinguish between:
   - Direct support (explicitly confirms the claim)
   - Indirect support (provides contextual support)
   - Direct contradiction (explicitly refutes or contradicts the claim)
   - Irrelevant, ambiguous, or outdated evidence
5. If evidence conflicts, explicitly identify and describe the conflict in your explanation.
6. If evidence is missing, sparse, or too vague to make a determination, return INSUFFICIENT_EVIDENCE or INCONCLUSIVE.
7. NEVER output hidden chain-of-thought, private reasoning scratchpads, or token traces. Provide a concise, clear, evidence-grounded explanation.

VERDICT OPTIONS:
- "SUPPORTED": The evidence decisively confirms the factual assertion.
- "CONTRADICTED": The evidence decisively refutes or contradicts the factual assertion.
- "PARTIALLY_SUPPORTED": Some aspects are confirmed but other assertions are unverified or inaccurate.
- "INCONCLUSIVE": Evidence is conflicting or ambiguous, precluding a clear conclusion.
- "INSUFFICIENT_EVIDENCE": Available evidence is too sparse, vague, or off-topic to verify the claim.

OUTPUT FORMAT:
Output MUST be a single valid JSON object with the following schema:
{
  "verdict": "SUPPORTED" | "CONTRADICTED" | "PARTIALLY_SUPPORTED" | "INCONCLUSIVE" | "INSUFFICIENT_EVIDENCE",
  "confidence": 0.85,
  "explanation": "Concise summary of why the evidence leads to this verdict.",
  "supporting_evidence_ids": ["evidence-id-1"],
  "contradicting_evidence_ids": ["evidence-id-2"],
  "uncertainty": "Any temporal caveats, conflicting details, or nuanced ambiguities (or null if none)."
}
"""


class GeminiVerificationProvider(BaseVerificationProvider):
    """
    Real verification provider using Google Gemini / OpenAI-compatible endpoint.
    Performs grounded claim verification against Phase 5 retrieved evidence passages.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = getattr(settings, "LLM_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "LLM_MODEL", "") or "gemini-3.6-flash"
        self.base_url = (
            base_url
            or getattr(settings, "LLM_BASE_URL", "")
            or "https://generativelanguage.googleapis.com/v1beta/openai"
        ).rstrip("/")

    @property
    def provider_name(self) -> str:
        return "gemini" if "generativelanguage" in self.base_url else "openai"

    @property
    def model_name(self) -> str:
        return self.model

    async def verify_claim(
        self,
        claim_input: ClaimVerificationInput,
    ) -> VerificationOutput:
        # Pre-compute objective evidence sufficiency and strength
        sufficiency, strength, temporal_notes = evidence_sufficiency_evaluator.evaluate(
            claim_text=claim_input.claim_text,
            evidence_items=claim_input.evidence_items,
        )

        # If zero evidence was retrieved, return INSUFFICIENT_EVIDENCE without LLM call
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

        if not self.api_key:
            raise LLMProviderUnavailableException(
                message=f"API key is not configured for {self.provider_name.upper()} verification provider.",
                code="LLM_PROVIDER_UNAVAILABLE",
                investigation_id=claim_input.investigation_id,
            )

        # Format evidence items for prompt
        evidence_prompt_lines = []
        valid_evidence_ids = set()
        for idx, ev in enumerate(claim_input.evidence_items, 1):
            valid_evidence_ids.add(ev.evidence_id)
            pub_info = f" [Publisher: {ev.publisher}]" if ev.publisher else ""
            date_info = f" [Published: {ev.publication_date}]" if ev.publication_date else ""
            stance_info = f" [Preliminary Stance: {ev.preliminary_stance}]" if ev.preliminary_stance else ""
            evidence_prompt_lines.append(
                f"[Evidence ID: {ev.evidence_id}]\n"
                f"Source: {ev.source_title or ev.source_url}{pub_info}{date_info}{stance_info}\n"
                f"Excerpt: \"{ev.exact_excerpt}\"\n"
            )

        user_content = (
            f"CLAIM TO VERIFY:\n\"{claim_input.claim_text}\"\n\n"
            f"CLAIM CONTEXT:\n{claim_input.context or 'None provided'}\n\n"
            f"AVAILABLE EVIDENCE ITEMS ({len(claim_input.evidence_items)}):\n"
            f"{chr(10).join(evidence_prompt_lines)}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Try primary model and compatible models within the same Gemini/OpenAI provider family
        candidate_models = [self.model]
        if self.provider_name == "gemini":
            for fallback_m in ("gemini-3-flash-preview", "gemini-flash-lite-latest", "gemini-3.7-flash"):
                if fallback_m not in candidate_models:
                    candidate_models.append(fallback_m)

        data = None
        effective_model = self.model
        last_exception = None

        for model_candidate in candidate_models:
            payload = {
                "model": model_candidate,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            max_retries = 3
            model_succeeded = False

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=40.0) as client:
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            effective_model = model_candidate
                            model_succeeded = True
                            break
                        elif resp.status_code in (429, 503):
                            # Check if daily quota is completely exhausted for this specific model
                            resp_text = resp.text
                            if "PerDay" in resp_text or "quotaValue" in resp_text:
                                logger.warning(
                                    f"Model {model_candidate} daily quota exhausted. Checking next provider model..."
                                )
                                break
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2.0 * (attempt + 1))
                                continue
                        last_exception = LLMProviderUnavailableException(
                            message=f"{self.provider_name.capitalize()} verification API error HTTP {resp.status_code}: {resp.text[:200]}",
                            code="LLM_PROVIDER_ERROR",
                            investigation_id=claim_input.investigation_id,
                        )
                except httpx.RequestError as exc:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    last_exception = LLMProviderUnavailableException(
                        message=f"Network error communicating with {self.provider_name.capitalize()} verification provider: {exc}",
                        code="LLM_PROVIDER_NETWORK_ERROR",
                        investigation_id=claim_input.investigation_id,
                    )

            if model_succeeded:
                break

        if not data or "choices" not in data or not data["choices"]:
            if last_exception:
                raise last_exception
            raise LLMProviderUnavailableException(
                message=f"Empty response from {self.provider_name.capitalize()} verification provider.",
                code="LLM_PROVIDER_EMPTY_RESPONSE",
                investigation_id=claim_input.investigation_id,
            )

        raw_json_str = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(raw_json_str)
        except json.JSONDecodeError as exc:
            logger.error(f"Malformed JSON returned by verification LLM: {raw_json_str[:300]}")
            raise LLMProviderUnavailableException(
                message="Verification provider returned non-JSON format.",
                code="LLM_MALFORMED_OUTPUT",
                investigation_id=claim_input.investigation_id,
            ) from exc

        # Parse & sanitize fields
        verdict = str(parsed.get("verdict", "INCONCLUSIVE")).upper().strip()
        allowed_verdicts = {
            "SUPPORTED",
            "CONTRADICTED",
            "REFUTED",
            "PARTIALLY_SUPPORTED",
            "INCONCLUSIVE",
            "INSUFFICIENT_EVIDENCE",
        }
        if verdict not in allowed_verdicts:
            verdict = "INCONCLUSIVE"
        if verdict == "REFUTED":
            verdict = "CONTRADICTED"

        confidence = float(parsed.get("confidence", 0.70))
        confidence = round(max(0.0, min(1.0, confidence)), 4)

        explanation = str(parsed.get("explanation", "Verification completed based on retrieved evidence."))

        # Filter evidence IDs to ensure they only contain actual input evidence IDs
        raw_supp = parsed.get("supporting_evidence_ids", [])
        raw_cont = parsed.get("contradicting_evidence_ids", [])

        supporting_ids = [str(eid) for eid in raw_supp if str(eid) in valid_evidence_ids]
        contradicting_ids = [str(eid) for eid in raw_cont if str(eid) in valid_evidence_ids]

        # If LLM didn't tag evidence IDs explicitly, infer from preliminary stance
        if not supporting_ids and not contradicting_ids:
            for ev in claim_input.evidence_items:
                if ev.preliminary_stance == "SUPPORTING" and verdict in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                    supporting_ids.append(ev.evidence_id)
                elif ev.preliminary_stance == "CONTRADICTING" and verdict in ("CONTRADICTED", "PARTIALLY_SUPPORTED"):
                    contradicting_ids.append(ev.evidence_id)

        uncertainty = parsed.get("uncertainty")
        if temporal_notes:
            uncertainty = f"{uncertainty}; {temporal_notes}" if uncertainty else temporal_notes

        return VerificationOutput(
            verdict=verdict,
            confidence=confidence,
            evidence_sufficiency=sufficiency,
            evidence_strength=strength,
            explanation=explanation,
            supporting_evidence_ids=supporting_ids,
            contradicting_evidence_ids=contradicting_ids,
            uncertainty=uncertainty,
            model_provider=f"{self.provider_name}:{effective_model}",
        )
