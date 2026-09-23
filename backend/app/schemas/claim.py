from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    EVENT = "EVENT"
    STATISTIC = "STATISTIC"
    DATE = "DATE"
    LOCATION = "LOCATION"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    QUOTE = "QUOTE"
    SCIENTIFIC = "SCIENTIFIC"
    ECONOMIC = "ECONOMIC"
    POLITICAL = "POLITICAL"
    PRODUCT = "PRODUCT"
    OTHER = "OTHER"


class ClaimStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    DECOMPOSING = "DECOMPOSING"
    TASKS_CREATED = "TASKS_CREATED"
    READY_FOR_RETRIEVAL = "READY_FOR_RETRIEVAL"
    FAILED = "FAILED"


class SourcePreference(str, Enum):
    OFFICIAL = "OFFICIAL"
    GOVERNMENT = "GOVERNMENT"
    ACADEMIC = "ACADEMIC"
    PRIMARY_SOURCE = "PRIMARY_SOURCE"
    REPUTABLE_NEWS = "REPUTABLE_NEWS"
    FACT_CHECK = "FACT_CHECK"


class VerificationTaskPlan(BaseModel):
    task_description: str = Field(..., description="Targeted verification question or sub-task.")
    search_query: str = Field(..., description="Future planned search query for evidence retrieval.")
    source_preferences: List[SourcePreference] = Field(
        default_factory=list,
        description="Recommended source types for future retrieval.",
    )
    task_status: str = Field(default="pending", description="Task lifecycle status.")


class ClaimTaskItem(BaseModel):
    id: str
    claim_id: str
    task_description: str
    search_query: Optional[str] = None
    task_status: str = "pending"
    completion_time: Optional[str] = None
    created_at: Optional[str] = None


class ExtractedClaimCandidate(BaseModel):
    claim_text: str = Field(..., description="Atomic factual assertion.")
    claim_type: ClaimType = Field(default=ClaimType.OTHER, description="Claim taxonomy classification.")
    context: Optional[str] = Field(default=None, description="Original sentence or paragraph context.")
    extraction_confidence: Optional[float] = Field(default=None, description="Confidence of claim extraction (NOT verification confidence).")
    language: str = Field(default="en", description="Language of the claim statement.")
    temporal_info: Optional[str] = Field(default=None, description="Detected temporal anchor (year, date, period).")
    entities: List[str] = Field(default_factory=list, description="Extracted named entities (people, orgs, places).")
    verification_tasks: List[VerificationTaskPlan] = Field(
        default_factory=list,
        description="Planned verification dimensions and future search queries.",
    )


class ClaimDetailResponse(BaseModel):
    id: str
    investigation_id: str
    claim_text: str
    claim_type: str = "OTHER"
    language: str = "en"
    context: Optional[str] = None
    order_index: int = 0
    extraction_confidence: Optional[float] = None
    status: str = "extracted"
    tasks: List[ClaimTaskItem] = Field(default_factory=list)
    created_at: Optional[str] = None

    # Backwards compatibility with Phase 1 ClaimItem
    @property
    def claim_id(self) -> str:
        return self.id

    @property
    def statement(self) -> str:
        return self.claim_text


# Backwards compatibility alias for Phase 1
ClaimItem = ClaimDetailResponse


class ClaimListResponse(BaseModel):
    investigation_id: str
    claims: List[ClaimDetailResponse] = Field(default_factory=list)
    total: int = 0
    request_id: str
