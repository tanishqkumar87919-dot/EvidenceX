import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .api.v1.router import api_v1_router
from .core.config import settings
from .core.errors import register_error_handlers
from .core.logging import logger

from contextlib import asynccontextmanager
from .database.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

# Initialize DB tables at startup
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal AI Claim Verification & Evidence Intelligence Backend",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Register custom exception handlers (standardizes errors across all endpoints)
register_error_handlers(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Frontend static files
import os
from fastapi.staticfiles import StaticFiles
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
if os.path.exists(_frontend_dir):
    app.mount("/frontend", StaticFiles(directory=_frontend_dir, html=True), name="frontend")



@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    Middleware that:
    1. Generates or extracts X-Request-ID
    2. Attaches request_id to request.state and response headers
    3. Records structured logs with latency and status without sensitive data
    """
    client_req_id = request.headers.get("X-Request-ID")
    request_id = client_req_id.strip() if client_req_id and client_req_id.strip() else str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unhandled exception processing {request.method} {request.url.path}: {exc}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "endpoint": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        raise exc

    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"{request.method} {request.url.path} {response.status_code} - {duration_ms}ms",
        extra={
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    return response


# Include API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", summary="Root Health & Metadata")
def root(request: Request):
    request_id = getattr(request.state, "request_id", "unknown-request-id")
    return {
        "service": settings.APP_NAME,
        "status": "online",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "request_id": request_id,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=(settings.APP_ENV == "development"),
    )
