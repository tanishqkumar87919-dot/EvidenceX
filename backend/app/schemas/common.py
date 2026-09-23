from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class InputModality(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    URL = "URL"
    AUDIO = "AUDIO"


class ExecutionMode(str, Enum):
    LIVE = "LIVE"
    DEMO = "DEMO"


class VerificationDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class EvidencePreference(str, Enum):
    BALANCED = "balanced"
    OFFICIAL = "official"


class ServiceNotReadyResponse(BaseModel):
    status: str = Field(
        default="service_not_ready",
        description="Indicates that the underlying pipeline is not implemented yet.",
    )
    message: str = Field(
        default="Verification service is not implemented yet.",
        description="Explanatory message regarding implementation phase.",
    )
    request_id: str = Field(..., description="Correlation request ID.")
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode requested (LIVE or DEMO).",
    )
    modality: Optional[InputModality] = Field(
        default=None, description="Input modality processed."
    )


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
