from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
    """Standardized representation of a single web search discovery."""
    title: str
    url: str
    snippet: str
    domain: str
    publisher: Optional[str] = None
    relevance_hint: float = 0.5
    published_date: Optional[datetime] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class WebSearchProvider(ABC):
    """Abstract interface for pluggable search engines (DuckDuckGo, Tavily, Google, Mock)."""

    @property
    def provider_name(self) -> str:
        return getattr(self, "_provider_name", "unknown")

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Executes search query and returns ranked search result candidates."""
        pass
