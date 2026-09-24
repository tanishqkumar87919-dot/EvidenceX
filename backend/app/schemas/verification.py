from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VerdictType(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceSufficiencyLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class ClaimVerificationResultItem(BaseModel):
    verification_id: str = Field(..., description="Unique ID of the verification result.")
    claim_id: str = Field(..., description="ID of the verified claim.")
    claim_text: str = Field(..., description="The exact factual assertion evaluated.")
    verdict: str = Field(..., description="The structured verdict: SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, INCONCLUSIVE, or INSUFFICIENT_EVIDENCE.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence in the verdict.")
    evidence_sufficiency: str = Field(..., description="Sufficiency assessment: HIGH, MEDIUM, LOW, or INSUFFICIENT.")
    evidence_strength: float = Field(..., ge=0.0, le=1.0, description="Aggregate strength of available evidence.")
    explanation: str = Field(..., description="Concise, evidence-grounded explanation of the assessment.")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence supporting the claim.")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence contradicting the claim.")
    uncertainty: Optional[str] = Field(default=None, description="Identified nuances, temporal caveats, or ambiguities.")
    model_provider: Optional[str] = Field(default=None, description="LLM/verification provider used.")
    created_at: str = Field(..., description="ISO 8601 timestamp of generation.")


class InvestigationVerificationResponse(BaseModel):
    investigation_id: str = Field(..., description="Target investigation ID.")
    status: str = Field(..., description="Updated investigation lifecycle status.")
    claims_verified: int = Field(..., description="Number of claims verified in this execution.")
    results: List[ClaimVerificationResultItem] = Field(default_factory=list, description="Verification assessments for claims.")
    request_id: str = Field(..., description="Request correlation ID.")


class InvestigationVerificationListResponse(BaseModel):
    investigation_id: str = Field(..., description="Target investigation ID.")
    results: List[ClaimVerificationResultItem] = Field(default_factory=list, description="List of persisted verification results.")
    total: int = Field(..., description="Total verification results for this investigation.")
    request_id: str = Field(..., description="Request correlation ID.")


class ClaimVerificationDetailResponse(BaseModel):
    claim_id: str = Field(..., description="Claim ID.")
    investigation_id: str = Field(..., description="Parent investigation ID.")
    result: Optional[ClaimVerificationResultItem] = Field(default=None, description="Verification result if available.")
    request_id: str = Field(..., description="Request correlation ID.")
