import asyncio
from typing import List, Optional
import httpx

from ...core.config import settings
from .base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Real vector embedding provider using Google Gemini's `gemini-embedding-001`.
    Uses the OpenAI-compatible endpoint with dimensions=768 for pgvector compatibility.
    """

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/embeddings"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: int = 768,
    ):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "LLM_API_KEY", "")
        self.model = model or getattr(settings, "EMBEDDING_MODEL", "gemini-embedding-001")
        self._dimensions = dimensions or getattr(settings, "EMBEDDING_DIMENSIONS", 768)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self.model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured for GeminiEmbeddingProvider.")

        # Batch in groups of up to 16 texts
        batch_size = 16
        all_embeddings: List[List[float]] = []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            payload = {
                "model": self.model,
                "input": chunk,
                "dimensions": self._dimensions,
            }

            max_retries = 3
            data = None
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        resp = await client.post(self.ENDPOINT, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            break
                        elif resp.status_code in (429, 503):
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        raise RuntimeError(f"Gemini embedding API returned HTTP {resp.status_code}: {resp.text[:200]}")
                except httpx.RequestError as exc:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Failed to communicate with Gemini embedding endpoint: {exc}") from exc

            if not data:
                raise RuntimeError("Failed to generate Gemini embeddings after retries.")

            # Extract vectors ordered by index
            records = sorted(data.get("data", []), key=lambda r: r.get("index", 0))
            for item in records:
                all_embeddings.append(item.get("embedding", []))

        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        results = await self.embed_texts([query])
        if not results:
            raise RuntimeError(f"Failed to generate query embedding for: {query[:50]}")
        return results[0]
