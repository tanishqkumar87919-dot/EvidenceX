from typing import List, Optional
from pydantic import BaseModel, Field


class TimelineEventItem(BaseModel):
    event_id: str
    event_type: str
    timestamp: Optional[str] = None
    title: str
    description: str
    source_id: Optional[str] = None
    claim_id: Optional[str] = None
    relationship: Optional[str] = None


class InvestigationTimelineResponse(BaseModel):
    investigation_id: str
    events: List[TimelineEventItem] = Field(default_factory=list)
    total: int = 0
    total_events: int = 0
    request_id: str


# Aliases for backwards compatibility
TimelineEvent = TimelineEventItem
TimelineResponse = InvestigationTimelineResponse
