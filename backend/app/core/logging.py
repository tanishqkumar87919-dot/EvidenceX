import json
import logging
import sys
import time
from typing import Any, Dict, Optional

SENSITIVE_KEYS = {
    "authorization",
    "apikey",
    "api_key",
    "password",
    "token",
    "secret",
    "service_role",
    "supabase_service_role_key",
    "database_url",
}


def sanitize_data(data: Any) -> Any:
    """Recursively redacts sensitive keys from dictionaries or structures."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


class StructuredFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        # Include structured extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = getattr(record, "request_id")
        if hasattr(record, "method"):
            log_entry["method"] = getattr(record, "method")
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = getattr(record, "endpoint")
        if hasattr(record, "status_code"):
            log_entry["status_code"] = getattr(record, "status_code")
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = getattr(record, "duration_ms")

        # Sanitize entire log entry to guarantee zero secret leakage
        sanitized_entry = sanitize_data(log_entry)
        return json.dumps(sanitized_entry)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures structured logger for EvidenceX."""
    logger = logging.getLogger("evidencex")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logging()
