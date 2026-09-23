from typing import Optional
from pydantic import BaseModel, Field


class UserSettings(BaseModel):
    theme: str = Field(
        default="light",
        pattern="^(light|dark)$",
        description="UI theme preference: 'light' or 'dark'.",
    )
    language: str = Field(
        default="en",
        pattern="^(en|hi)$",
        description="Interface language: 'en' (English) or 'hi' (Hindi).",
    )
    default_depth: str = Field(
        default="standard",
        pattern="^(quick|standard|deep)$",
        description="Default verification depth: quick, standard, or deep.",
    )
    evidence_preference: str = Field(
        default="balanced",
        pattern="^(balanced|official)$",
        description="Evidence source preference: balanced or official.",
    )
    analytics_opt_in: bool = Field(
        default=True,
        description="Whether user opts into anonymous aggregated analytics.",
    )
    telemetry_enabled: bool = Field(
        default=False,
        description="Whether telemetry is enabled.",
    )
    auto_investigate: bool = Field(
        default=False,
        description="Auto trigger multi-hop investigation pipeline upon upload.",
    )


class SettingsResponse(BaseModel):
    settings: UserSettings
    request_id: str
