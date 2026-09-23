import hashlib
import ipaddress
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ...core.errors import BadRequestException
from ...schemas.common import ExecutionMode, InputModality
from ...schemas.ingest import NormalizedInput
from ...schemas.verify import UrlVerifyRequest
from ..language import detect_language


def compute_content_hash(content: str) -> str:
    """Computes SHA-256 hash for content deduplication."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class UrlService:
    """
    Secure URL Ingestion Service with SSRF protection, safe redirect validation,
    response-size streaming caps, and article content extraction.
    """

    MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
    FETCH_TIMEOUT_SECONDS = 10.0
    MAX_REDIRECTS = 3

    BLOCKED_HOSTNAMES = {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "169.254.169.254",
        "metadata.google.internal",
        "instance-data",
    }

    def validate_url(self, raw_url: str) -> str:
        """
        Validates URL syntax and performs DNS SSRF checks against private/internal/cloud networks.
        """
        if not raw_url or not str(raw_url).strip():
            raise BadRequestException(message="URL cannot be empty.", code="EMPTY_URL")

        url_str = str(raw_url).strip()
        parsed = urlparse(url_str)

        if not parsed.scheme or parsed.scheme.lower() not in ("http", "https"):
            raise BadRequestException(
                message="Invalid URL scheme. Only HTTP and HTTPS URLs are accepted.",
                code="INVALID_URL_SCHEME",
            )

        hostname = (parsed.hostname or "").lower().strip()
        if not hostname:
            raise BadRequestException(
                message="Invalid URL format. Hostname is missing.",
                code="INVALID_URL_HOST",
            )

        # Check hostname blacklist
        if hostname in self.BLOCKED_HOSTNAMES or hostname.endswith((".local", ".internal", ".lan", ".corp")):
            raise BadRequestException(
                message="Access to internal/private network addresses is blocked for security.",
                code="SSRF_ATTEMPT_DETECTED",
            )

        # DNS Resolution and IP validation
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise BadRequestException(
                message=f"Unable to resolve host: {hostname}",
                code="URL_DNS_RESOLUTION_FAILED",
            )

        for entry in addr_info:
            ip_str = entry[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or str(ip) == "169.254.169.254"
            ):
                raise BadRequestException(
                    message="Access to internal/private network addresses is blocked for security.",
                    code="SSRF_ATTEMPT_DETECTED",
                )

        return url_str

    async def fetch_url(self, url: str) -> Tuple[str, str]:
        """
        Safely fetches URL content with SSRF checks on every redirect and response-size limit.
        Returns (html_content, final_url).
        """
        current_url = url
        redirect_count = 0

        async with httpx.AsyncClient(
            timeout=self.FETCH_TIMEOUT_SECONDS,
            follow_redirects=False,
            headers={"User-Agent": "EvidenceX-Bot/1.0 (+https://evidencex.org)"},
        ) as client:
            while redirect_count <= self.MAX_REDIRECTS:
                self.validate_url(current_url)

                try:
                    response = await client.get(current_url)
                except httpx.TimeoutException:
                    raise BadRequestException(
                        message=f"Timeout reached while fetching URL: {current_url}",
                        code="URL_TIMEOUT",
                    )
                except Exception as e:
                    raise BadRequestException(
                        message=f"Network error while fetching URL: {str(e)}",
                        code="URL_FETCH_ERROR",
                    )

                # Check for redirects
                if response.is_redirect:
                    redirect_target = response.headers.get("Location")
                    if not redirect_target:
                        raise BadRequestException(
                            message="Redirect header missing from server response.",
                            code="URL_REDIRECT_ERROR",
                        )
                    current_url = urljoin(current_url, redirect_target)
                    redirect_count += 1
                    continue

                if response.status_code >= 400:
                    raise BadRequestException(
                        message=f"Target URL returned HTTP status {response.status_code}.",
                        code="URL_HTTP_ERROR",
                    )

                # Validate Content-Type
                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ("text/html", "application/xhtml+xml", "text/plain")):
                    raise BadRequestException(
                        message=f"Target URL returned unsupported content type: {content_type}",
                        code="UNSUPPORTED_URL_CONTENT",
                    )

                content_bytes = response.content
                if len(content_bytes) > self.MAX_RESPONSE_BYTES:
                    raise BadRequestException(
                        message="URL response size exceeds maximum allowed limit of 5 MB.",
                        code="URL_RESPONSE_TOO_LARGE",
                    )

                return response.text, current_url

            raise BadRequestException(
                message=f"Exceeded maximum allowed redirects ({self.MAX_REDIRECTS}).",
                code="TOO_MANY_REDIRECTS",
            )

    def extract_content(self, html: str, final_url: str) -> Dict[str, Any]:
        """
        Extracts title, article body, publisher, publication date, author, and canonical URL.
        """
        soup = BeautifulSoup(html, "html.parser")

        # 1. Title
        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()

        # 2. Canonical URL
        canonical = None
        canon_tag = soup.find("link", rel="canonical")
        if canon_tag and canon_tag.get("href"):
            canonical = canon_tag["href"].strip()

        # 3. Author
        author = None
        author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()

        # 4. Publication Date
        pub_date = None
        date_meta = (
            soup.find("meta", property="article:published_time")
            or soup.find("meta", attrs={"name": "pubdate"})
            or soup.find("meta", attrs={"name": "publication_date"})
        )
        if date_meta and date_meta.get("content"):
            pub_date = date_meta["content"].strip()

        # 5. Publisher / Domain
        domain = urlparse(final_url).netloc
        publisher = None
        site_name_meta = soup.find("meta", property="og:site_name")
        if site_name_meta and site_name_meta.get("content"):
            publisher = site_name_meta["content"].strip()
        else:
            publisher = domain

        # 6. Extract Main Body Text
        # Strip script, style, navigation, footer, forms, header
        for elem in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form", "svg"]):
            elem.decompose()

        # Prioritize <article> or <main>
        main_container = soup.find("article") or soup.find("main") or soup.find("div", class_=lambda c: c and any(k in str(c).lower() for k in ("article", "post-content", "entry-content", "story-body")))

        target_root = main_container if main_container else soup.body or soup
        paragraphs = [p.get_text().strip() for p in target_root.find_all("p") if len(p.get_text().strip()) > 15]

        if paragraphs:
            body_text = "\n\n".join(paragraphs)
        else:
            body_text = target_root.get_text(separator="\n").strip()

        # Clean multiple whitespaces
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        cleaned_body = "\n\n".join(lines)

        if not cleaned_body or len(cleaned_body) < 20:
            raise BadRequestException(
                message="Could not extract readable article text from the provided URL.",
                code="EMPTY_EXTRACTION",
            )

        return {
            "title": title,
            "text": cleaned_body,
            "canonical_url": canonical or final_url,
            "domain": domain,
            "publisher": publisher,
            "author": author,
            "published_at": pub_date,
        }

    async def process(self, payload: UrlVerifyRequest) -> NormalizedInput:
        """
        Validates URL, fetches HTML securely, extracts article metadata and text,
        and constructs NormalizedInput.
        """
        raw_url = str(payload.url)
        validated_url = self.validate_url(raw_url)

        html, final_url = await self.fetch_url(validated_url)
        extracted = self.extract_content(html, final_url)

        extracted_text = extracted["text"]
        lang = detect_language(extracted_text)
        content_hash = compute_content_hash(extracted_text)

        eff_inv_id = (
            payload.investigation_id.strip()
            if payload.investigation_id and payload.investigation_id.strip()
            else f"inv_{uuid.uuid4().hex[:12]}"
        )

        metadata = {
            "title": extracted["title"],
            "canonical_url": extracted["canonical_url"],
            "domain": extracted["domain"],
            "publisher": extracted["publisher"],
            "author": extracted["author"],
            "published_at": extracted["published_at"],
            "char_count": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "depth": payload.depth.value if hasattr(payload.depth, "value") else str(payload.depth),
            "evidence_preference": payload.evidence_preference.value if hasattr(payload.evidence_preference, "value") else str(payload.evidence_preference),
        }

        return NormalizedInput(
            investigation_id=eff_inv_id,
            input_type=InputModality.URL,
            input_mode=payload.mode if isinstance(payload.mode, ExecutionMode) else ExecutionMode(payload.mode),
            text=extracted_text,
            url=final_url,
            language=lang,
            metadata=metadata,
            content_hash=content_hash,
            received_at=datetime.now(timezone.utc),
        )


url_service = UrlService()
