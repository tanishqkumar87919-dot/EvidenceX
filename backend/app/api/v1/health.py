from fastapi import APIRouter
from typing import Dict, Any
import time
from ...core.config import settings
from ...database.session import check_supabase_connectivity, check_postgres_connectivity

router = APIRouter()

@router.get("/health", summary="System Health & Readiness Check")
async def get_health() -> Dict[str, Any]:
    """
    Returns actual backend status and readiness checks for database & Supabase.
    Transparently reports unconfigured or unreachable states.
    """
    start_time = time.time()
    
    # Real checks
    supabase_status = check_supabase_connectivity()
    postgres_status = check_postgres_connectivity()
    
    # Determine overall status
    is_ready = supabase_status.get("connected", False) or postgres_status.get("connected", False)
    overall_status = "operational" if is_ready else ("degraded" if settings.APP_ENV == "development" else "unhealthy")
    
    return {
        "status": overall_status,
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": time.time(),
        "components": {
            "backend": {
                "status": "operational",
                "uptime_check": "ok"
            },
            "supabase": supabase_status,
            "database": postgres_status
        }
    }
