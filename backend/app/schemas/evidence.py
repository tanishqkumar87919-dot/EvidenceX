from typing import List, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: str
    claim_id: Optional[str] = None
    source_title: str
    source_url: str
    publisher: str
    snippet: str
    stance: str = Field(
        description="Relationship to claim: supporting, contradicting, neutral."
    )
    reliability_score: Optional[float] = None
    published_date: Optional[str] = None


class EvidenceListResponse(BaseModel):
    investigation_id: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    total: int = 0
    request_id: str


class SourceItem(BaseModel):
    source_id: str
    url: str
    title: Optional[str] = None
    publisher: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[str] = None
    retrieved_date: Optional[str] = None


class SourceListResponse(BaseModel):
    investigation_id: str
    sources: List[SourceItem] = Field(default_factory=list)
    total: int = 0
    request_id: str

