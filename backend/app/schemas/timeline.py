from typing import List, Optional
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    event_id: str
    investigation_id: str
    timestamp: str
    title: str
    description: str
    source_url: Optional[str] = None
    event_type: str = Field(
        default="evidence",
        description="Event classification: claim_origin, corroboration, debunk, etc.",
    )


class TimelineResponse(BaseModel):
    investigation_id: str
    events: List[TimelineEvent] = Field(default_factory=list)
    total: int = 0
    request_id: str
