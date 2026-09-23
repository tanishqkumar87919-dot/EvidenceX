from typing import Any, Optional
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import logger


class EvidenceXException(Exception):
    """Base exception for all EvidenceX operational errors."""

    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        status_code: int = 400,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class ServiceNotReadyException(EvidenceXException):
    def __init__(
        self,
        message: str = "The requested service is not implemented yet in Phase 1.",
        code: str = "SERVICE_NOT_READY",
        investigation_id: Optional[str] = None,
        input_type: Optional[str] = None,
        input_mode: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        self.investigation_id = investigation_id
        self.input_type = input_type
        self.input_mode = input_mode
        super().__init__(
            message=message,
            code=code,
            status_code=501,
            details=details,
        )


class UnsupportedMediaException(EvidenceXException):
    def __init__(
        self,
        message: str = "The uploaded media type is unsupported.",
        code: str = "UNSUPPORTED_MEDIA_TYPE",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=415,
            details=details,
        )


class PayloadTooLargeException(EvidenceXException):
    def __init__(
        self,
        message: str = "The payload exceeds the maximum allowed upload size.",
        code: str = "PAYLOAD_TOO_LARGE",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=413,
            details=details,
        )


class BadRequestException(EvidenceXException):
    def __init__(
        self,
        message: str = "Bad request parameters or payload.",
        code: str = "BAD_REQUEST",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=400,
            details=details,
        )


class NotFoundException(EvidenceXException):
    def __init__(
        self,
        message: str = "The requested resource was not found.",
        code: str = "NOT_FOUND",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=404,
            details=details,
        )


class TranscriptionFailedException(EvidenceXException):
    def __init__(
        self,
        message: str = "Audio transcription could not be completed.",
        code: str = "TRANSCRIPTION_FAILED",
        investigation_id: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        self.investigation_id = investigation_id
        super().__init__(
            message=message,
            code=code,
            status_code=422,
            details=details,
        )


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown-request-id")


async def evidencex_exception_handler(
    request: Request, exc: EvidenceXException
) -> JSONResponse:
    request_id = _get_request_id(request)
    status_str = "error"
    if exc.code == "SERVICE_NOT_READY":
        status_str = "service_not_ready"
    elif exc.code == "TRANSCRIPTION_FAILED":
        status_str = "transcription_failed"

    content: dict = {
        "status": status_str,
        "message": exc.message,
        "request_id": request_id,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "request_id": request_id,
            "details": exc.details,
        },
    }
    if hasattr(exc, "investigation_id") and exc.investigation_id:
        content["investigation_id"] = exc.investigation_id
    if hasattr(exc, "input_type") and exc.input_type:
        content["input_type"] = exc.input_type
        content["modality"] = exc.input_type
    if hasattr(exc, "input_mode") and exc.input_mode:
        content["input_mode"] = exc.input_mode
        content["mode"] = exc.input_mode

    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = _get_request_id(request)
    formatted_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        formatted_errors.append(
            {"field": loc, "issue": err.get("msg"), "type": err.get("type")}
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed. Please inspect details for format rules.",
                "request_id": request_id,
                "details": formatted_errors,
            }
        },
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = _get_request_id(request)
    # Map status code to standard error code
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_SERVER_ERROR",
        501: "SERVICE_NOT_READY",
        503: "SERVICE_UNAVAILABLE",
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": exc.detail or "An HTTP error occurred.",
                "request_id": request_id,
                "details": None,
            }
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.error(
        f"Unhandled server error: {exc}",
        extra={
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method,
        },
    )
    # Strictly do NOT expose stack traces or internals to the client
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "request_id": request_id,
                "details": None,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(EvidenceXException, evidencex_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
