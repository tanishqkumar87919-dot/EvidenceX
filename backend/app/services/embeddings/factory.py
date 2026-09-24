from typing import Optional

from ...core.config import settings
from .base import EmbeddingProvider
from .gemini_provider import GeminiEmbeddingProvider
from .local_provider import LocalDeterministicEmbeddingProvider


def get_embedding_provider(provider_name: Optional[str] = None) -> EmbeddingProvider:
    """
    Factory returning the configured vector embedding provider.
    Defaults to 'gemini' (gemini-embedding-001) in LIVE mode, or 'local' in test environments.
    """
    provider = (
        provider_name
        or getattr(settings, "EMBEDDING_PROVIDER", None)
        or "gemini"
    ).lower()

    if provider == "gemini":
        return GeminiEmbeddingProvider()
    elif provider in ("local", "mock"):
        return LocalDeterministicEmbeddingProvider()
    else:
        return GeminiEmbeddingProvider()
