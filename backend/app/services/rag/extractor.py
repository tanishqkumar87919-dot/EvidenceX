import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup


@dataclass
class ExtractedDocument:
    """Cleaned article / document content parsed from an external web page."""
    url: str
    title: str
    body_text: str
    headings: List[str] = field(default_factory=list)
    author: Optional[str] = None
    publication_date: Optional[datetime] = None
    canonical_url: Optional[str] = None
    publisher: Optional[str] = None
    character_count: int = 0
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentExtractor:
    """
    Cleans raw HTML markup into structured article text.
    Strips boilerplate, ads, scripts, navigations, and extracts metadata.
    """

    STRIP_TAGS = [
        "script", "style", "nav", "footer", "header", "noscript",
        "form", "aside", "svg", "button", "iframe", "menu"
    ]

    def extract(self, html: str, url: str) -> ExtractedDocument:
        if not html or not html.strip():
            return ExtractedDocument(url=url, title="", body_text="", character_count=0, word_count=0)

        soup = BeautifulSoup(html, "html.parser")

        # 1. Remove noise elements
        for tag in soup(self.STRIP_TAGS):
            tag.decompose()

        # 2. Extract Title
        title = ""
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # 3. Extract Canonical URL
        canonical_url = None
        canon_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
        if canon_tag and canon_tag.get("href"):
            canonical_url = canon_tag["href"].strip()

        # 4. Extract Meta Information (Author, Date, Publisher)
        author = self._extract_meta(soup, ["author", "article:author", "byl", "twitter:creator"])
        publisher = self._extract_meta(soup, ["og:site_name", "publisher", "twitter:site"])
        pub_date_str = self._extract_meta(soup, [
            "article:published_time", "publication_date", "date",
            "sailthru.date", "dc.date", "parsely-pub-date"
        ])
        pub_date = self._parse_date(pub_date_str)

        # 5. Extract Headings
        headings: List[str] = []
        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            h_text = h.get_text(strip=True)
            if h_text and len(h_text) > 3 and h_text not in headings:
                headings.append(h_text)

        # 6. Extract Main Body Paragraphs
        paragraphs: List[str] = []
        # Target article or main containers if present
        container = soup.find("article") or soup.find("main") or soup.body or soup

        for p in container.find_all(["p", "li"]):
            text = " ".join(p.get_text().split())
            # Filter trivial copyright or cookie snippets
            if len(text) > 30 and not any(k in text.lower() for k in ["cookie policy", "terms of use", "privacy policy", "all rights reserved"]):
                if text not in paragraphs:
                    paragraphs.append(text)

        body_text = "\n\n".join(paragraphs)
        if not body_text:
            # Fallback to general text
            body_text = " ".join(container.get_text().split())

        char_count = len(body_text)
        word_count = len(body_text.split())

        return ExtractedDocument(
            url=url,
            title=title,
            body_text=body_text,
            headings=headings[:10],
            author=author,
            publication_date=pub_date,
            canonical_url=canonical_url,
            publisher=publisher,
            character_count=char_count,
            word_count=word_count,
            metadata={
                "extracted_paragraphs_count": len(paragraphs),
                "has_canonical": bool(canonical_url),
            },
        )

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, property_names: List[str]) -> Optional[str]:
        for prop in property_names:
            meta = soup.find("meta", attrs={"name": prop}) or soup.find("meta", attrs={"property": prop})
            if meta and meta.get("content"):
                return meta["content"].strip()
        return None

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        # ISO formats or common web formats
        date_str = date_str.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ):
            try:
                dt = datetime.strptime(date_str[:19], fmt[:19])
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        return None


document_extractor = DocumentExtractor()
