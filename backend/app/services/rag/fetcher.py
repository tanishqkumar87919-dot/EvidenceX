import asyncio
from dataclasses import dataclass
from typing import Optional
import httpx


@dataclass
class FetchResult:
    """Outcome of fetching an external webpage."""
    url: str
    status_code: int
    content: Optional[str] = None
    content_type: Optional[str] = None
    final_url: Optional[str] = None
    error: Optional[str] = None
    success: bool = False


class SourceFetcher:
    """
    Robust async HTTP fetcher for external source pages.
    Enforces response size limits, timeouts, redirect policies, and content type validation.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 EvidenceX/1.0"
    )
    MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    DEFAULT_TIMEOUT = 12.0

    async def fetch_page(self, url: str, max_retries: int = 2) -> FetchResult:
        if not url or not url.startswith(("http://", "https://")):
            return FetchResult(url=url, status_code=400, error="Invalid URL protocol", success=False)

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.DEFAULT_TIMEOUT,
                    follow_redirects=True,
                    max_redirects=5,
                    verify=False,  # Avoid failing on non-standard SSL certificates for public news
                ) as client:
                    resp = await client.get(url, headers=headers)

                    if resp.status_code != 200:
                        if resp.status_code in (429, 503) and attempt < max_retries:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        return FetchResult(
                            url=url,
                            status_code=resp.status_code,
                            final_url=str(resp.url),
                            error=f"HTTP {resp.status_code}",
                            success=False,
                        )

                    c_type = resp.headers.get("content-type", "").lower()
                    if not any(t in c_type for t in ("text/html", "application/xhtml+xml", "text/plain")):
                        return FetchResult(
                            url=url,
                            status_code=resp.status_code,
                            content_type=c_type,
                            error=f"Unsupported content-type: {c_type}",
                            success=False,
                        )

                    body = resp.text
                    if len(body.encode("utf-8")) > self.MAX_BYTES:
                        body = body[: self.MAX_BYTES]

                    return FetchResult(
                        url=url,
                        status_code=200,
                        content=body,
                        content_type=c_type,
                        final_url=str(resp.url),
                        success=True,
                    )
            except httpx.TimeoutException:
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                return FetchResult(url=url, status_code=408, error="Connection timed out", success=False)
            except Exception as exc:
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                return FetchResult(url=url, status_code=500, error=str(exc), success=False)

        return FetchResult(url=url, status_code=500, error="Max retries exceeded", success=False)


source_fetcher = SourceFetcher()
