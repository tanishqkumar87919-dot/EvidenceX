import urllib.parse
from datetime import datetime
from typing import List, Optional
import httpx

from .base import SearchResult, WebSearchProvider


class TavilySearchProvider(WebSearchProvider):
    """
    Search provider using the Tavily Research Search API.
    Used when SEARCH_PROVIDER=tavily and WEB_SEARCH_API_KEY / SEARCH_API_KEY is configured.
    """

    API_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.api_key or not query or not query.strip():
            return []

        payload = {
            "api_key": self.api_key,
            "query": query.strip(),
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }

        results: List[SearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self.API_URL, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("results", []):
                        url = r.get("url", "")
                        domain = urllib.parse.urlparse(url).netloc.lower()
                        results.append(
                            SearchResult(
                                title=r.get("title", ""),
                                url=url,
                                snippet=r.get("content", ""),
                                domain=domain,
                                raw_metadata={"score": r.get("score"), "engine": "tavily"},
                            )
                        )
        except Exception:
            return results

        return results
