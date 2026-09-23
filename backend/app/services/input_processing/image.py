import hashlib
import io
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytesseract
from fastapi import UploadFile
from PIL import Image

from ...core.config import settings
from ...core.errors import BadRequestException
from ...core.security import validate_uploaded_file
from ...schemas.common import ExecutionMode, InputModality
from ...schemas.ingest import NormalizedInput
from ...schemas.verify import VerifyFormMetadata
from ..language import detect_language


def compute_bytes_hash(data: bytes) -> str:
    """Computes SHA-256 hash for binary content deduplication."""
    return hashlib.sha256(data).hexdigest()


class OCREngineInterface(ABC):
    @abstractmethod
    def extract_text(self, img: Image.Image) -> Dict[str, Any]:
        """Extracts text, confidence, regions, and detected language from image."""
        pass


class TesseractOCREngine(OCREngineInterface):
    """
    Tesseract OCR implementation supporting English and Hindi text extraction
    with bounding boxes and per-word confidence metrics.
    """

    def extract_text(self, img: Image.Image) -> Dict[str, Any]:
        try:
            # Check available tesseract languages
            avail_langs = pytesseract.get_languages()
            lang_param = "eng"
            if "hin" in avail_langs:
                lang_param = "eng+hin"

            # Extract detailed bounding box and confidence data
            data = pytesseract.image_to_data(
                img,
                lang=lang_param,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            raise BadRequestException(
                message=f"OCR engine processing failed: {str(e)}",
                code="OCR_PROCESSING_FAILED",
            )

        n_boxes = len(data.get("text", []))
        words: List[str] = []
        confidences: List[float] = []
        regions: List[Dict[str, Any]] = []

        current_line_words: List[str] = []
        last_line_num = -1

        for i in range(n_boxes):
            text = (data["text"][i] or "").strip()
            conf = float(data["conf"][i])

            if text and conf >= 0:
                words.append(text)
                confidences.append(conf)

                line_num = data["line_num"][i]
                if line_num != last_line_num and current_line_words:
                    current_line_words = []
                    last_line_num = line_num

                current_line_words.append(text)
                regions.append({
                    "text": text,
                    "confidence": round(conf / 100.0, 4),
                    "box": {
                        "left": data["left"][i],
                        "top": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                    },
                })

        extracted_text = pytesseract.image_to_string(img, lang=lang_param).strip()

        if not extracted_text:
            raise BadRequestException(
                message="No readable text could be detected in the uploaded image.",
                code="NO_TEXT_DETECTED_IN_IMAGE",
            )

        avg_confidence = (
            round(sum(confidences) / len(confidences) / 100.0, 4)
            if confidences
            else 0.0
        )

        return {
            "text": extracted_text,
            "confidence": avg_confidence,
            "regions_count": len(regions),
            "regions": regions[:50],  # Return up to 50 bounding boxes in metadata
            "ocr_engine": "tesseract",
            "ocr_lang": lang_param,
        }


class ImageService:
    """
    Image & Screenshot Ingestion Service with format validation, dimensions checking,
    corrupted file detection, and real OCR text extraction.
    """

    def __init__(self):
        # Default engine is Tesseract (verified working on system)
        self.ocr_engine: OCREngineInterface = TesseractOCREngine()

    def validate_image(self, file: UploadFile) -> Tuple[bytes, Image.Image]:
        content = validate_uploaded_file(
            file=file,
            max_bytes=settings.MAX_IMAGE_SIZE_BYTES,
            allowed_mimes=settings.ALLOWED_IMAGE_MIME_TYPES,
            allowed_extensions=settings.ALLOWED_IMAGE_EXTENSIONS,
        )

        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            # Reload image after verify() as recommended by PIL
            img = Image.open(io.BytesIO(content))
        except Exception as e:
            raise BadRequestException(
                message=f"Uploaded image is corrupted or invalid: {str(e)}",
                code="CORRUPTED_IMAGE",
            )

        width, height = img.size
        if width < 10 or height < 10:
            raise BadRequestException(
                message=f"Image dimensions ({width}x{height}) are too small for processing.",
                code="IMAGE_TOO_SMALL",
            )
        if width > 10000 or height > 10000:
            raise BadRequestException(
                message=f"Image dimensions ({width}x{height}) exceed maximum allowed 10,000px limit.",
                code="IMAGE_TOO_LARGE",
            )

        return content, img

    def process(
        self,
        file: UploadFile,
        investigation_id: Optional[str] = None,
        depth: str = "standard",
        mode: ExecutionMode = ExecutionMode.LIVE,
        evidence_preference: str = "balanced",
    ) -> NormalizedInput:
        """
        Validates uploaded image, runs real OCR, detects language,
        and constructs NormalizedInput.
        """
        raw_bytes, img = self.validate_image(file)

        # Execute OCR
        ocr_result = self.ocr_engine.extract_text(img)
        extracted_text = ocr_result["text"]

        # Detect language of extracted text
        lang = detect_language(extracted_text)

        content_hash = compute_bytes_hash(raw_bytes)
        _, ext = os.path.splitext(file.filename.lower() if file.filename else ".png")
        sanitized_ref = f"images/{content_hash[:16]}{ext}"

        eff_inv_id = (
            investigation_id.strip()
            if investigation_id and investigation_id.strip()
            else f"inv_{uuid.uuid4().hex[:12]}"
        )

        metadata = {
            "original_filename": file.filename,
            "mime_type": file.content_type,
            "dimensions": {"width": img.width, "height": img.height},
            "format": img.format,
            "ocr_confidence": ocr_result["confidence"],
            "ocr_engine": ocr_result["ocr_engine"],
            "ocr_lang": ocr_result["ocr_lang"],
            "regions_count": ocr_result["regions_count"],
            "regions": ocr_result["regions"],
            "depth": depth,
            "evidence_preference": evidence_preference,
        }

        return NormalizedInput(
            investigation_id=eff_inv_id,
            input_type=InputModality.IMAGE,
            input_mode=mode,
            text=extracted_text,
            image_reference=sanitized_ref,
            language=lang,
            metadata=metadata,
            content_hash=content_hash,
            received_at=datetime.now(timezone.utc),
        )


image_service = ImageService()
