import time
from typing import Dict, Any
import httpx
from ..core.config import settings

def check_supabase_connectivity() -> Dict[str, Any]:
    """
    Checks real connectivity to Supabase.
    Does NOT return healthy unless verified.
    """
    if not settings.SUPABASE_URL or not (settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY):
        return {
            "status": "unconfigured",
            "message": "SUPABASE_URL and SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY are not configured.",
            "connected": False
        }
    
    # Try connecting to Supabase REST health endpoint
    start_time = time.time()
    try:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY}"
        }
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url, headers=headers)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            if resp.status_code in [200, 404]: # REST base root responding
                return {
                    "status": "operational",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "endpoint": settings.SUPABASE_URL
                }
            else:
                return {
                    "status": "error",
                    "connected": False,
                    "status_code": resp.status_code,
                    "message": resp.text[:200]
                }
    except Exception as e:
        return {
            "status": "unreachable",
            "connected": False,
            "error": str(e)
        }

def check_postgres_connectivity() -> Dict[str, Any]:
    """
    Checks direct PostgreSQL connection via DATABASE_URL if configured.
    """
    if not settings.DATABASE_URL:
        return {
            "status": "unconfigured",
            "message": "DATABASE_URL is not configured in environment.",
            "connected": False
        }
    
    # Note: Requires asyncpg or psycopg2 / sqlalchemy installed
    try:
        import psycopg2 # type: ignore
        start_time = time.time()
        conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=4)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        cur.close()
        conn.close()
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "operational",
            "connected": True,
            "latency_ms": latency_ms
        }
    except ImportError:
        return {
            "status": "driver_missing",
            "connected": False,
            "message": "psycopg2 / asyncpg driver not installed."
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }
