from typing import Any, Dict
from urllib.parse import urlparse
from ...core.errors import BadRequestException, ServiceNotReadyException


class UrlService:
    """
    URL verification and scraper service abstraction.
    In Phase 1: Validates URL syntax without scraping or generating fake claims.
    """

    def validate_url(self, url: str) -> str:
        if not url or not url.strip():
            raise BadRequestException(
                message="URL cannot be empty.",
                code="EMPTY_URL",
            )
        parsed = urlparse(url.strip())
        if not parsed.scheme or parsed.scheme.lower() not in ("http", "https"):
            raise BadRequestException(
                message="Invalid URL scheme. Only HTTP and HTTPS URLs are accepted.",
                code="INVALID_URL_SCHEME",
            )
        if not parsed.netloc:
            raise BadRequestException(
                message="Invalid URL format. Hostname is missing.",
                code="INVALID_URL_HOST",
            )
        return url.strip()

    def process(self, url: str, mode: str = "LIVE") -> Dict[str, Any]:
        self.validate_url(url)
        # Phase 1: Do NOT implement web scraping or verification
        raise ServiceNotReadyException(
            message="URL verification and article extraction service is not implemented yet in Phase 1."
        )


url_service = UrlService()
