import urllib.parse
from datetime import datetime, timezone
from typing import List
import httpx
from bs4 import BeautifulSoup

from .base import SearchResult, WebSearchProvider


class DuckDuckGoSearchProvider(WebSearchProvider):
    """
    Real live web search provider using DuckDuckGo.
    Requires zero external API credentials.
    Parses live search engine results into clean SearchResult models.
    """

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        data = {"q": query.strip()}

        results: List[SearchResult] = []
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.post(self.SEARCH_URL, data=data, headers=headers)
                if resp.status_code != 200:
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                entries = soup.select(".result__body")

                for entry in entries:
                    if len(results) >= max_results:
                        break

                    title_el = entry.select_one(".result__title a")
                    snippet_el = entry.select_one(".result__snippet")

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    raw_href = title_el.get("href", "")

                    # DuckDuckGo wraps destination in /l/?uddg=...
                    clean_url = self._extract_clean_url(raw_href)
                    if not clean_url or not clean_url.startswith("http"):
                        continue

                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    domain = urllib.parse.urlparse(clean_url).netloc.lower()

                    results.append(
                        SearchResult(
                            title=title,
                            url=clean_url,
                            snippet=snippet,
                            domain=domain,
                            published_date=None,
                            raw_metadata={"engine": "duckduckgo", "query": query},
                        )
                    )
        except Exception:
            # Transparent fallback / empty return on network error
            return results

        return results

    @staticmethod
    def _extract_clean_url(raw_href: str) -> str:
        """Unwraps DuckDuckGo redirect link to canonical destination URL."""
        if not raw_href:
            return ""
        if "uddg=" in raw_href:
            parsed = urllib.parse.urlparse(raw_href)
            params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in params and params["uddg"]:
                return params["uddg"][0]
        if raw_href.startswith("//"):
            return "https:" + raw_href
        return raw_href
