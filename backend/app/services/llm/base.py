from abc import ABC, abstractmethod
from typing import List

from ...schemas.claim import ExtractedClaimCandidate


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM / NLP claim extraction and decomposition providers.
    Both external LLMs (OpenAI, Gemini, Groq) and local NLP extractor implement this contract.
    """

    @abstractmethod
    async def extract_and_decompose_claims(
        self,
        text: str,
        investigation_id: str,
        language: str = "en",
    ) -> List[ExtractedClaimCandidate]:
        """
        Extracts factual claims from raw or normalized text, decomposes compound claims
        into atomic verifiable units, classifies each claim into a taxonomy category,
        generates verification questions and search query tasks, and returns candidates.
        """
        pass
