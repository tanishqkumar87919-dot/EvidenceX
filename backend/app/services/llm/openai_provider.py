import asyncio
import json
from typing import List, Optional
import httpx

from ...core.config import settings
from ...core.errors import (
    ClaimExtractionException,
    EvidenceXException,
    LLMProviderUnavailableException,
)
from ...schemas.claim import (
    ClaimType,
    ExtractedClaimCandidate,
    SourcePreference,
    VerificationTaskPlan,
)
from .base import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    """
    External LLM Provider using OpenAI / OpenAI-compatible Chat Completions API
    (e.g., OpenAI, Groq, Ollama, DeepSeek).
    Validates API key and cleanly raises LLMProviderUnavailableException when credentials
    are absent or when remote endpoint is unreachable.
    """

    SYSTEM_PROMPT = """You are EvidenceX Claim Extractor and Decomposer.
Your task is to analyze the input text and extract all verifiable factual claims.
For each claim:
1. Decompose compound statements into atomic, independently verifiable claims.
2. Separate opinions, commentary, rhetorical questions, greetings, boilerplate, or noise from verifiable facts.
3. Classify each claim into one of these exact types: EVENT, STATISTIC, DATE, LOCATION, PERSON, ORGANIZATION, QUOTE, SCIENTIFIC, ECONOMIC, POLITICAL, PRODUCT, OTHER.
4. For each atomic claim, generate 1 to 2 specific verification tasks:
   - task_description: What specific question needs to be answered?
   - search_query: A targeted keyword query for evidence retrieval.
   - source_preferences: Recommended source categories (OFFICIAL, GOVERNMENT, ACADEMIC, PRIMARY_SOURCE, REPUTABLE_NEWS, FACT_CHECK).
5. Output MUST be valid JSON with the exact structure:
{
  "claims": [
    {
      "claim_text": "Atomic factual assertion",
      "claim_type": "SCIENTIFIC",
      "context": "Original sentence",
      "extraction_confidence": 0.95,
      "language": "en",
      "temporal_info": "2023",
      "entities": ["NASA", "James Webb Space Telescope"],
      "verification_tasks": [
        {
          "task_description": "Did the James Webb Space Telescope detect CO2 on WASP-39 b?",
          "search_query": "James Webb Space Telescope WASP-39 b carbon dioxide",
          "source_preferences": ["OFFICIAL", "ACADEMIC"]
        }
      ]
    }
  ]
}
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or settings.LLM_MODEL or "gpt-4o-mini"
        self.base_url = (base_url or settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")

    async def extract_and_decompose_claims(
        self,
        text: str,
        investigation_id: str,
        language: str = "en",
    ) -> List[ExtractedClaimCandidate]:
        if not self.api_key:
            provider_label = "Gemini" if "generativelanguage" in self.base_url else "OpenAI"
            raise LLMProviderUnavailableException(
                message=f"{provider_label} / External LLM API key is not configured.",
                code="LLM_PROVIDER_UNAVAILABLE",
                investigation_id=investigation_id,
            )

        if not text or not text.strip():
            return []

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Input text (Language: {language}):\n{text.strip()}"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        data = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        break
                    elif response.status_code in (429, 503):
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue

                    raise LLMProviderUnavailableException(
                        message=f"External LLM API returned status {response.status_code}: {response.text[:200]}",
                        code="LLM_PROVIDER_UNAVAILABLE",
                        investigation_id=investigation_id,
                    )
            except httpx.RequestError as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                raise LLMProviderUnavailableException(
                    message=f"Failed to communicate with external LLM provider: {str(exc)}",
                    code="LLM_PROVIDER_UNAVAILABLE",
                    investigation_id=investigation_id,
                ) from exc
            except EvidenceXException:
                raise
            except Exception as exc:
                raise ClaimExtractionException(
                    message=f"Claim extraction encountered an unexpected error: {str(exc)}",
                    code="CLAIM_EXTRACTION_FAILED",
                    investigation_id=investigation_id,
                ) from exc

        if not data:
            raise LLMProviderUnavailableException(
                message="External LLM API was unavailable after retries.",
                code="LLM_PROVIDER_UNAVAILABLE",
                investigation_id=investigation_id,
            )

        try:
            content_str = data["choices"][0]["message"]["content"]
            parsed = json.loads(content_str)
            raw_claims = parsed.get("claims", [])

            candidates: List[ExtractedClaimCandidate] = []
            for item in raw_claims:
                claim_type_str = item.get("claim_type", "OTHER").upper()
                try:
                    ctype = ClaimType(claim_type_str)
                except ValueError:
                    ctype = ClaimType.OTHER

                tasks: List[VerificationTaskPlan] = []
                for t in item.get("verification_tasks", []):
                    src_prefs = []
                    for sp in t.get("source_preferences", []):
                        try:
                            src_prefs.append(SourcePreference(sp.upper()))
                        except ValueError:
                            pass
                    if not src_prefs:
                        src_prefs = [SourcePreference.REPUTABLE_NEWS]

                    tasks.append(
                        VerificationTaskPlan(
                            task_description=t.get("task_description", f"Verify: {item.get('claim_text', '')}"),
                            search_query=t.get("search_query", item.get("claim_text", "")),
                            source_preferences=src_prefs,
                            task_status="pending",
                        )
                    )

                candidates.append(
                    ExtractedClaimCandidate(
                        claim_text=item.get("claim_text", "").strip(),
                        claim_type=ctype,
                        context=item.get("context", text[:100]),
                        extraction_confidence=float(item.get("extraction_confidence", 0.85)),
                        language=item.get("language", language),
                        temporal_info=item.get("temporal_info"),
                        entities=item.get("entities", []),
                        verification_tasks=tasks,
                    )
                )
            return candidates

        except Exception as exc:
            raise ClaimExtractionException(
                message=f"Failed to parse structured JSON from LLM: {str(exc)}",
                code="CLAIM_EXTRACTION_FAILED",
                investigation_id=investigation_id,
            ) from exc
