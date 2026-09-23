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
    
    start_time = time.time()
    try:
        # If service role key is available, check REST API; if anon key, check Auth settings endpoint
        if settings.SUPABASE_SERVICE_ROLE_KEY:
            url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/"
            key = settings.SUPABASE_SERVICE_ROLE_KEY
        else:
            url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/settings"
            key = settings.SUPABASE_ANON_KEY

        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}"
        }
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=headers)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            if resp.status_code == 200:
                return {
                    "status": "operational",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "endpoint": settings.SUPABASE_URL,
                    "auth_role": "service_role" if settings.SUPABASE_SERVICE_ROLE_KEY else "anon"
                }
            elif resp.status_code == 404:
                return {
                    "status": "operational",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "endpoint": settings.SUPABASE_URL,
                    "auth_role": "anon"
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
    
    try:
        import psycopg2  # type: ignore
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
            "message": "psycopg2 driver not installed."
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }
