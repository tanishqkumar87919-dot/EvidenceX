from typing import List, Optional
from pydantic import BaseModel, Field


class ClaimItem(BaseModel):
    claim_id: str
    investigation_id: str
    statement: str
    verdict: Optional[str] = Field(
        default=None,
        description="Verdict for this atomic claim (supported, refuted, unverified).",
    )
    confidence: Optional[float] = Field(
        default=None, description="Confidence score between 0.0 and 1.0."
    )
    created_at: Optional[str] = None


class ClaimListResponse(BaseModel):
    investigation_id: str
    claims: List[ClaimItem] = Field(default_factory=list)
    total: int = 0
    request_id: str
