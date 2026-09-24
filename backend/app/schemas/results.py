from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceReferenceItem(BaseModel):
    evidence_id: str
    excerpt: str
    source_title: str
    source_url: str
    domain: Optional[str] = None
    source_category: Optional[str] = None
    source_quality: Optional[str] = None
    relevance_score: Optional[float] = None
    publication_date: Optional[str] = None
    stance: str = "supporting"


class ClaimResultItem(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str = "OTHER"
    verdict: str
    confidence: float
    evidence_sufficiency: str
    evidence_strength: float
    reason: str
    supporting_evidence: List[EvidenceReferenceItem] = Field(default_factory=list)
    contradicting_evidence: List[EvidenceReferenceItem] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class ResultSummary(BaseModel):
    total_claims: int = 0
    supported: int = 0
    contradicted: int = 0
    partially_supported: int = 0
    inconclusive: int = 0
    insufficient_evidence: int = 0
    average_confidence: float = 0.0
    overall_verdict: str = "INCONCLUSIVE"
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    source_count: int = 0


class InvestigationResultsResponse(BaseModel):
    investigation_id: str
    status: str
    total_claims: int = 0
    verified_claims: int = 0
    summary: ResultSummary
    claims: List[ClaimResultItem] = Field(default_factory=list)
    overall_verdict: str
    average_confidence: float
    created_at: Optional[str] = None
    request_id: str
