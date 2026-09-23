from ...core.config import settings
from .base import BaseLLMProvider
from .local_nlp import LocalNLPClaimExtractor
from .openai_provider import OpenAILLMProvider


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """
    Factory function returning the configured claim extraction and decomposition LLM provider.
    Defaults to 'local' deterministic NLP extractor.
    """
    provider = (provider_name or settings.LLM_PROVIDER or "local").lower()
    if provider == "openai":
        return OpenAILLMProvider()
    elif provider == "gemini":
        # Gemini OpenAI-compatible endpoint
        base_url = settings.LLM_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai"
        model = settings.LLM_MODEL if settings.LLM_MODEL not in ("gpt-4o-mini", "") else "gemini-3.6-flash"
        api_key = settings.LLM_API_KEY or getattr(settings, "GEMINI_API_KEY", "")
        return OpenAILLMProvider(api_key=api_key, model=model, base_url=base_url)
    elif provider == "local":
        return LocalNLPClaimExtractor()
    else:
        # Default fallback to robust local NLP
        return LocalNLPClaimExtractor()


__all__ = [
    "BaseLLMProvider",
    "LocalNLPClaimExtractor",
    "OpenAILLMProvider",
    "get_llm_provider",
]
