import hashlib
import math
from typing import List

from .base import EmbeddingProvider


class LocalDeterministicEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic local embedding provider generating normalized 768-dim vectors.
    Produces semantically correlated vectors for similar text via character/token hashing.
    Used for offline unit test suites and fallback scenarios.
    """

    def __init__(self, dimensions: int = 768, dimension: int = None):
        self._dimensions = dimension if dimension is not None else dimensions


    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def dimension(self) -> int:
        return self._dimensions


    @property
    def model_name(self) -> str:
        return "local-deterministic-768"

    @property
    def provider_name(self) -> str:
        return "local_hash"


    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._compute_vector(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        return self._compute_vector(query)

    def _compute_vector(self, text: str) -> List[float]:
        vec = [0.0] * self._dimensions
        if not text:
            return vec

        tokens = text.lower().split()
        for token in tokens:
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimensions
            sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
            vec[idx] += sign

        # Add bigram hashes for phrases
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i+1]}"
            h = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimensions
            sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
            vec[idx] += sign * 1.5

        # Normalize to unit vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        else:
            vec[0] = 1.0
        return vec


# Alias for testing and hashing
LocalHashingEmbeddingProvider = LocalDeterministicEmbeddingProvider

