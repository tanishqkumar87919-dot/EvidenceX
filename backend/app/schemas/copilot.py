from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .common import ExecutionMode


class CopilotQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User investigation inquiry.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Session conversation thread ID.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO.",
    )


class CopilotQueryResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    request_id: str
