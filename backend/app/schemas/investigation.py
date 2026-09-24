from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .common import EvidencePreference, ExecutionMode, InputModality, VerificationDepth


class InvestigationCreateRequest(BaseModel):
    modality: InputModality = Field(
        ..., description="Input modality: TEXT, IMAGE, URL, or AUDIO."
    )
    title: Optional[str] = Field(
        default=None, max_length=200, description="Optional investigation title."
    )
    content: Optional[str] = Field(
        default=None,
        description="Raw text, URL, or description of content under investigation.",
    )
    depth: VerificationDepth = Field(
        default=VerificationDepth.STANDARD,
        description="Investigation depth level.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO.",
    )
    evidence_preference: EvidencePreference = Field(
        default=EvidencePreference.BALANCED,
        description="Evidence source preference.",
    )
    retrieve_evidence: bool = Field(
        default=False,
        description="Whether to immediately execute evidence retrieval after claim extraction.",
    )


class InvestigationStatusResponse(BaseModel):
    investigation_id: str
    status: str
    progress_percent: int
    current_stage: str
    request_id: str


class InvestigationDetailResponse(BaseModel):
    investigation_id: str
    title: Optional[str] = None
    status: str
    modality: InputModality
    mode: ExecutionMode
    created_at: Optional[str] = None
    claims_count: int = 0
    request_id: str
