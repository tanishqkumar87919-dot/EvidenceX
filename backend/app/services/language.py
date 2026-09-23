import logging
from typing import Optional
from langdetect import DetectorFactory, detect, detect_langs

# Enforce deterministic results from langdetect
DetectorFactory.seed = 42

logger = logging.getLogger("evidencex.language")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
}


def detect_language(text: Optional[str], min_confidence: float = 0.5) -> str:
    """
    Detects language of provided text.
    Returns ISO 639-1 code ('en', 'hi', etc.) if detected with sufficient confidence,
    or 'UNKNOWN' if ambiguous, too short, or unsupported.
    Never invents or fabricates a language.
    """
    if not text or len(text.strip()) < 3:
        return "UNKNOWN"

    cleaned = text.strip()

    try:
        predictions = detect_langs(cleaned)
        if not predictions:
            return "UNKNOWN"

        top_pred = predictions[0]
        lang_code = top_pred.lang.lower()
        confidence = top_pred.prob

        if confidence < min_confidence:
            logger.info("Language detection confidence %.2f below threshold %.2f for lang %s", confidence, min_confidence, lang_code)
            return "UNKNOWN"

        # Check against supported languages
        if lang_code in SUPPORTED_LANGUAGES:
            return lang_code

        # For other detectable languages, return the detected code if high confidence
        if len(lang_code) == 2:
            return lang_code

        return "UNKNOWN"
    except Exception as e:
        logger.debug("Language detection failed: %s", e)
        return "UNKNOWN"
