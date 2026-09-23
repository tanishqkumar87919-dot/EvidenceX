from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator

from .common import EvidencePreference, ExecutionMode, VerificationDepth


class TextVerifyRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=3,
        max_length=50000,
        description="The statement or content text to verify.",
    )
    depth: VerificationDepth = Field(
        default=VerificationDepth.STANDARD,
        description="Verification depth level.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO.",
    )
    evidence_preference: EvidencePreference = Field(
        default=EvidencePreference.BALANCED,
        description="Preferred evidence source weighting.",
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Text content cannot be empty or whitespace.")
        return stripped


class UrlVerifyRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="Public URL pointing to article or claim to verify.",
    )
    depth: VerificationDepth = Field(
        default=VerificationDepth.STANDARD,
        description="Verification depth level.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description="Execution mode: LIVE (default) or DEMO.",
    )
    evidence_preference: EvidencePreference = Field(
        default=EvidencePreference.BALANCED,
        description="Preferred evidence source weighting.",
    )


class VerifyFormMetadata(BaseModel):
    depth: VerificationDepth = VerificationDepth.STANDARD
    mode: ExecutionMode = ExecutionMode.LIVE
    evidence_preference: EvidencePreference = EvidencePreference.BALANCED
