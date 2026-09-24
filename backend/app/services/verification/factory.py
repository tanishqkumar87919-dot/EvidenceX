from typing import Optional
from ...core.config import settings
from .base import BaseVerificationProvider
from .gemini_provider import GeminiVerificationProvider
from .local_provider import DeterministicVerificationProvider


def get_verification_provider(provider_name: Optional[str] = None) -> BaseVerificationProvider:
    """
    Factory creating the active verification provider.
    In LIVE mode, uses Gemini / external LLM provider.
    In test / offline mode, returns DeterministicVerificationProvider.
    """
    provider = (
        provider_name
        or getattr(settings, "VERIFICATION_PROVIDER", None)
        or getattr(settings, "LLM_PROVIDER", None)
        or "gemini"
    ).lower()

    if provider in ("local", "mock", "deterministic"):
        return DeterministicVerificationProvider()
    elif provider in ("gemini", "openai"):
        return GeminiVerificationProvider()
    else:
        return GeminiVerificationProvider()
