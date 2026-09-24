from typing import Any, Dict, List, Optional
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

    # Phase 7 Evidence Explorer extensions
    domain: Optional[str] = None
    source_category: Optional[str] = None
    source_quality: Optional[str] = None
    authority: Optional[float] = None
    retrieved_date: Optional[str] = None
    relevance_score: Optional[float] = None
    relationship: Optional[str] = None
    excerpt: Optional[str] = None


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
    authority_score: Optional[float] = None
    credibility_score: Optional[float] = None


class SourceListResponse(BaseModel):
    investigation_id: str
    sources: List[SourceItem] = Field(default_factory=list)
    total: int = 0
    request_id: str


class AssociatedClaimItem(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: Optional[str] = None
    verdict: Optional[str] = None


class AssociatedVerificationResultItem(BaseModel):
    verification_result_id: str
    verdict: str
    confidence: Optional[float] = None
    explanation: Optional[str] = None


class EvidenceDetailResponse(BaseModel):
    evidence_id: str
    claim_id: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    publisher: Optional[str] = None
    snippet: str
    excerpt: Optional[str] = None
    stance: str
    reliability_score: Optional[float] = None
    relevance_score: Optional[float] = None
    published_date: Optional[str] = None
    created_at: Optional[str] = None
    source: Optional[SourceItem] = None
    associated_claims: List[AssociatedClaimItem] = Field(default_factory=list)
    associated_verification_results: List[AssociatedVerificationResultItem] = Field(default_factory=list)
    request_id: str
