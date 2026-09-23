import time
from typing import Any, Dict, Generator, Optional
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from ..core.config import settings
from .models import Base


def get_connection_url(raw_url: Optional[str] = None) -> str:
    url = raw_url or settings.DATABASE_URL
    if url and url.startswith("postgresql://"):
        # Use modern psycopg 3 driver for PostgreSQL
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not url:
        return "sqlite:///./evidencex_dev.db"
    return url


def create_db_engine(db_url: Optional[str] = None):
    url = get_connection_url(db_url)
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for acquiring database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind_engine=None) -> None:
    """Creates all database tables defined in Base metadata."""
    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)


def check_supabase_connectivity() -> Dict[str, Any]:
    """
    Checks real connectivity to Supabase.
    Does NOT return healthy unless verified.
    """
    if not settings.SUPABASE_URL or not (settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY):
        return {
            "status": "unconfigured",
            "message": "SUPABASE_URL and SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY are not configured.",
            "connected": False,
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
            "Authorization": f"Bearer {key}",
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
                    "auth_role": "service_role" if settings.SUPABASE_SERVICE_ROLE_KEY else "anon",
                }
            elif resp.status_code == 404:
                return {
                    "status": "operational",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "endpoint": settings.SUPABASE_URL,
                    "auth_role": "anon",
                }
            else:
                return {
                    "status": "error",
                    "connected": False,
                    "status_code": resp.status_code,
                    "message": resp.text[:200],
                }
    except Exception as e:
        return {
            "status": "unreachable",
            "connected": False,
            "error": str(e),
        }


def check_postgres_connectivity() -> Dict[str, Any]:
    """
    Checks direct PostgreSQL connection via DATABASE_URL if configured.
    """
    if not settings.DATABASE_URL:
        return {
            "status": "unconfigured",
            "message": "DATABASE_URL is not configured in environment.",
            "connected": False,
        }

    try:
        start_time = time.time()
        test_engine = create_db_engine()
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "operational",
            "connected": True,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e),
        }
