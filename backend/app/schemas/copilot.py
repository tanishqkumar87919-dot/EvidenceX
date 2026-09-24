from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from .common import ExecutionMode


class CopilotQueryRequest(BaseModel):
    message: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="User investigation inquiry.",
    )
    query: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Alternative field for user inquiry (backwards compatible).",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Session conversation thread ID.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO.",
    )

    @model_validator(mode="after")
    def validate_content_present(self):
        text = (self.message or "").strip() or (self.query or "").strip()
        if not text:
            raise ValueError("Inquiry text cannot be empty. Provide 'message' or 'query'.")
        if not self.message:
            self.message = text
        if not self.query:
            self.query = text
        return self


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_title: str
    url: str
    domain: Optional[str] = None
    excerpt: Optional[str] = None
    stance: Optional[str] = None


class ClaimCitation(BaseModel):
    claim_id: str
    claim_text: str
    verdict: Optional[str] = None


class CopilotResponse(BaseModel):
    investigation_id: str
    message: str
    answer: str
    evidence_references: List[EvidenceCitation] = Field(default_factory=list)
    claim_references: List[ClaimCitation] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.85
    conversation_id: Optional[str] = None
    uncertainty: Optional[str] = None
    created_at: Optional[str] = None
    request_id: str


class CopilotQueryResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    request_id: str


class CopilotMessageItem(BaseModel):
    id: str
    investigation_id: str
    role: str
    message: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None


class CopilotHistoryResponse(BaseModel):
    investigation_id: str
    messages: List[CopilotMessageItem] = Field(default_factory=list)
    total: int = 0
    total_messages: int = 0
    request_id: str
