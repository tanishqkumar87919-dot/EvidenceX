from fastapi import APIRouter

from .analytics import router as analytics_router
from .claims import router as claims_router
from .copilot import router as copilot_router
from .evidence import router as evidence_router
from .health import router as health_router
from .investigations import router as investigations_router
from .settings import router as settings_router
from .system import router as system_router
from .timeline import router as timeline_router
from .verify import router as verify_router

api_v1_router = APIRouter()

# Mount all v1 sub-routers
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(verify_router, tags=["Verification Contracts"])
api_v1_router.include_router(investigations_router, tags=["Investigation Contracts"])
api_v1_router.include_router(claims_router, tags=["Claim Contracts"])
api_v1_router.include_router(evidence_router, tags=["Evidence Contracts"])
api_v1_router.include_router(timeline_router, tags=["Timeline Contracts"])
api_v1_router.include_router(analytics_router, tags=["Analytics Contracts"])
api_v1_router.include_router(copilot_router, tags=["Copilot Contracts"])
api_v1_router.include_router(settings_router, tags=["Settings"])
api_v1_router.include_router(system_router, tags=["System Status"])

__all__ = ["api_v1_router"]
