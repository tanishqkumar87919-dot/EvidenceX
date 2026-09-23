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
