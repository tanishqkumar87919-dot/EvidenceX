from typing import Optional

from ...core.config import settings
from .base import WebSearchProvider
from .duckduckgo_provider import DuckDuckGoSearchProvider
from .mock_provider import MockSearchProvider
from .tavily_provider import TavilySearchProvider


def get_web_search_provider(provider_name: Optional[str] = None) -> WebSearchProvider:
    """
    Factory function instantiating the active WebSearchProvider.
    Defaults to DuckDuckGo (zero-config, keyless real search) or Tavily if key is configured.
    """
    provider = (
        provider_name
        or getattr(settings, "WEB_SEARCH_PROVIDER", None)
        or getattr(settings, "SEARCH_PROVIDER", None)
        or "duckduckgo"
    ).lower()

    api_key = getattr(settings, "WEB_SEARCH_API_KEY", "") or getattr(settings, "SEARCH_API_KEY", "")

    if provider == "tavily" and api_key:
        return TavilySearchProvider(api_key=api_key)
    elif provider == "mock":
        return MockSearchProvider()
    elif provider == "duckduckgo":
        return DuckDuckGoSearchProvider()
    else:
        # Default to DuckDuckGo for live execution
        return DuckDuckGoSearchProvider()


# Alias for convenience
get_search_provider = get_web_search_provider

