import os
from typing import Optional, Set
from fastapi import UploadFile

from .errors import (
    BadRequestException,
    PayloadTooLargeException,
    UnsupportedMediaException,
)


def validate_uploaded_file(
    file: UploadFile,
    max_bytes: int,
    allowed_mimes: Set[str],
    allowed_extensions: Set[str],
) -> bytes:
    """
    Validates an uploaded file against size, empty-file rules, MIME types, and file extensions.
    Returns the read bytes if valid.
    """
    if not file or not file.filename:
        raise BadRequestException(
            message="No file uploaded or file has no filename.",
            code="MISSING_FILE",
        )

    # Validate file extension
    _, ext = os.path.splitext(file.filename.lower())
    if not ext or ext not in allowed_extensions:
        raise UnsupportedMediaException(
            message=(
                f"File extension '{ext}' is not supported. "
                f"Allowed extensions: {', '.join(sorted(allowed_extensions))}"
            )
        )

    # Validate MIME type
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    # Some browsers may send application/octet-stream for audio/wav; allow if extension is valid and matches
    if content_type not in allowed_mimes and content_type != "application/octet-stream":
        raise UnsupportedMediaException(
            message=(
                f"Media type '{file.content_type}' is not supported. "
                f"Allowed MIME types: {', '.join(sorted(allowed_mimes))}"
            )
        )

    # Read content to check length and non-emptiness
    try:
        content = file.file.read()
    except Exception as e:
        raise BadRequestException(
            message=f"Failed to read uploaded file: {str(e)}",
            code="FILE_READ_ERROR",
        )

    if len(content) == 0:
        raise BadRequestException(
            message="The uploaded file is empty (0 bytes).",
            code="EMPTY_FILE",
        )

    if len(content) > max_bytes:
        max_mb = round(max_bytes / (1024 * 1024), 1)
        actual_mb = round(len(content) / (1024 * 1024), 2)
        raise PayloadTooLargeException(
            message=(
                f"File size ({actual_mb} MB) exceeds maximum allowed upload limit of {max_mb} MB."
            )
        )

    return content


def mask_secret(secret: Optional[str], unmasked_chars: int = 4) -> str:
    """Safely masks sensitive tokens or keys for audit/status inspection."""
    if not secret:
        return "not_configured"
    if len(secret) <= unmasked_chars:
        return "***"
    return f"{'*' * (len(secret) - unmasked_chars)}{secret[-unmasked_chars:]}"
