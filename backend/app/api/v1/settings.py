from fastapi import APIRouter, Request

from ...schemas.settings import SettingsResponse, UserSettings

router = APIRouter(prefix="/settings", tags=["User Settings"])

# Default settings instance (in-memory state for Phase 1, compatible with frontend)
_active_settings = UserSettings(
    theme="light",
    language="en",
    default_depth="standard",
    evidence_preference="balanced",
    analytics_opt_in=True,
    telemetry_enabled=False,
    auto_investigate=False,
)


@router.get("", response_model=SettingsResponse, summary="Get User Settings")
async def get_user_settings(request: Request) -> SettingsResponse:
    """
    Retrieves current user and interface settings.
    Strictly safe: does not expose internal infrastructure credentials.
    """
    request_id = getattr(request.state, "request_id", "unknown-request-id")
    return SettingsResponse(settings=_active_settings, request_id=request_id)


@router.put("", response_model=SettingsResponse, summary="Update User Settings")
async def update_user_settings(
    payload: UserSettings, request: Request
) -> SettingsResponse:
    """
    Updates user interface preferences (theme, language, depth, evidence bias).
    """
    global _active_settings
    _active_settings = payload
    request_id = getattr(request.state, "request_id", "unknown-request-id")
    return SettingsResponse(settings=_active_settings, request_id=request_id)
