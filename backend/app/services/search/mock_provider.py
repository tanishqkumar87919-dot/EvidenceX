from typing import List, Optional
from .base import SearchResult, WebSearchProvider


class MockSearchProvider(WebSearchProvider):
    """
    Configurable mock search provider for test environments.
    Guarantees deterministic search responses without outbound internet traffic.
    """

    def __init__(self, predefined_results: Optional[List[SearchResult]] = None):
        self.predefined_results = predefined_results or []
        self.last_query: Optional[str] = None

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        self.last_query = query
        if self.predefined_results:
            return self.predefined_results[:max_results]

        # Default sample search results for generic tests
        results = [
            SearchResult(
                title=f"Source Reference: {query[:30]}",
                url=f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')[:25]}_{i}",
                snippet=f"Detailed reference excerpt regarding {query}. This is informative context.",
                domain="wikipedia.org",
                publisher="Wikipedia",
                raw_metadata={"engine": "mock", "index": i},
            )
            for i in range(max_results)
        ]
        return results

