from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for vector embedding generation providers."""

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of text passages."""
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Generates a single embedding vector for a claim or search query."""
        pass

    async def embed_text(self, text: str) -> List[float]:
        """Convenience alias for embed_query."""
        return await self.embed_query(text)


    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Returns the dimensionality of the generated vectors."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the name/identifier of the active embedding model."""
        pass
