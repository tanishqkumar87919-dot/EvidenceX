from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class VerdictDistribution(BaseModel):
    supported: int = 0
    contradicted: int = 0
    partially_supported: int = 0
    inconclusive: int = 0
    insufficient_evidence: int = 0


class EvidenceSufficiencyDistribution(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    insufficient: int = 0


class RecentInvestigationItem(BaseModel):
    investigation_id: str
    title: Optional[str] = None
    status: str
    modality: str
    claims_count: int = 0
    sources_count: int = 0
    overall_verdict: Optional[str] = None
    created_at: Optional[str] = None


class TimeseriesDataPoint(BaseModel):
    date: str
    investigations_count: int = 0
    verified_claims_count: int = 0


class AnalyticsOverviewResponse(BaseModel):
    total_investigations: int = 0
    total_claims: int = 0
    total_verified_claims: int = 0
    supported_count: int = 0
    contradicted_count: int = 0
    partially_supported_count: int = 0
    inconclusive_count: int = 0
    insufficient_evidence_count: int = 0
    evidence_count: int = 0
    source_count: int = 0
    average_confidence: float = 0.0
    verdict_distribution: VerdictDistribution = Field(default_factory=VerdictDistribution)
    evidence_sufficiency_distribution: EvidenceSufficiencyDistribution = Field(
        default_factory=EvidenceSufficiencyDistribution
    )
    source_type_distribution: Dict[str, int] = Field(default_factory=dict)
    investigation_status_distribution: Dict[str, int] = Field(default_factory=dict)
    recent_investigations: List[RecentInvestigationItem] = Field(default_factory=list)
    timeseries: List[TimeseriesDataPoint] = Field(default_factory=list)
    request_id: str
