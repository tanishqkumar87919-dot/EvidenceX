from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceInput(BaseModel):
    """
    Standardized evidence representation passed to verification providers.
    Derived directly from Phase 5 persisted EvidenceModel and SourceModel.
    """
    evidence_id: str
    exact_excerpt: str
    source_url: str
    source_title: Optional[str] = None
    publisher: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = None
    credibility_weight: float = 0.5
    publication_date: Optional[str] = None
    relevance_score: Optional[float] = None
    preliminary_stance: str = "INCONCLUSIVE"


class ClaimVerificationInput(BaseModel):
    """
    Input package for verifying a single atomic claim.
    """
    investigation_id: str
    claim_id: str
    claim_text: str
    context: Optional[str] = None
    claim_type: Optional[str] = None
    evidence_items: List[EvidenceInput] = Field(default_factory=list)


class VerificationOutput(BaseModel):
    """
    Structured, explainable output from a verification provider.
    Distinguishes confidence, sufficiency, strength, and verdict.
    """
    verdict: str  # SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, INCONCLUSIVE, INSUFFICIENT_EVIDENCE
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_sufficiency: str  # HIGH, MEDIUM, LOW, INSUFFICIENT
    evidence_strength: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None
    model_provider: str


class BaseVerificationProvider(ABC):
    """
    Abstract interface for claim verification providers.
    Both external LLMs (Gemini, OpenAI) and deterministic local verification engines
    implement this contract.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    async def verify_claim(
        self,
        claim_input: ClaimVerificationInput,
    ) -> VerificationOutput:
        """
        Evaluates a claim against strictly supplied evidence items.
        Returns a structured VerificationOutput.
        """
        pass
