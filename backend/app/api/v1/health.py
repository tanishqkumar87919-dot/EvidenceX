from typing import Dict
from fastapi import APIRouter
from ...core.config import settings

router = APIRouter()


@router.get("/health", summary="Health Check")
async def get_health() -> Dict[str, str]:
    """
    Lightweight health check endpoint.
    Conforms strictly to Section 5: returns status, service, and version.
    Does NOT expose secrets, credentials, or internal topology.
    """
    return {
        "status": "healthy",
        "service": "EvidenceX Backend",
        "version": settings.APP_VERSION,
    }
