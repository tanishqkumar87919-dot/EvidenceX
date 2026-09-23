from typing import Any, Dict
from fastapi import UploadFile

from ...core.config import settings
from ...core.errors import ServiceNotReadyException
from ...core.security import validate_uploaded_file


class ImageService:
    """
    Image verification and OCR service abstraction.
    In Phase 1: Validates file constraints without running OCR or generating fake extractions.
    """

    def validate_image(self, file: UploadFile) -> bytes:
        return validate_uploaded_file(
            file=file,
            max_bytes=settings.MAX_IMAGE_SIZE_BYTES,
            allowed_mimes=settings.ALLOWED_IMAGE_MIME_TYPES,
            allowed_extensions=settings.ALLOWED_IMAGE_EXTENSIONS,
        )

    def process(self, file: UploadFile, mode: str = "LIVE") -> Dict[str, Any]:
        self.validate_image(file)
        # Phase 1: Do NOT implement OCR or image claim extraction
        raise ServiceNotReadyException(
            message="Image OCR and visual claim verification service is not implemented yet in Phase 1."
        )


image_service = ImageService()
