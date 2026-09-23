from typing import List, Set, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Metadata
    APP_NAME: str = "EvidenceX Backend API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_URL: str = "http://localhost:8000"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Execution Mode (LIVE or DEMO)
    DEFAULT_MODE: str = "LIVE"

    # CORS Origins (comma-separated string or list)
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000"

    # Upload Limits (bytes)
    MAX_AUDIO_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Allowed Media Types & Extensions
    ALLOWED_AUDIO_MIME_TYPES: Set[str] = {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
    }
    ALLOWED_AUDIO_EXTENSIONS: Set[str] = {
        ".mp3",
        ".wav",
        ".m4a",
        ".mp4",
        ".webm",
        ".ogg",
        ".flac",
    }

    ALLOWED_IMAGE_MIME_TYPES: Set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
    }
    ALLOWED_IMAGE_EXTENSIONS: Set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
    }

    # Supabase / Database Credentials (From Environment Variables Only)
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Future AI / Search / STT Provider Placeholders (Phases 2-5)
    SEARCH_PROVIDER: str = "tavily"
    SEARCH_API_KEY: str = ""
    FACT_CHECK_PROVIDER: str = "google_factcheck"
    FACT_CHECK_API_KEY: str = ""
    STT_PROVIDER: str = "whisper"
    WHISPER_MODEL: str = "tiny"
    STT_API_KEY: str = ""
    OCR_ENGINE: str = "tesseract"

    # LLM & Agentic Claim Extraction (Phase 4)
    LLM_PROVIDER: str = "local"  # options: local, openai, gemini
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [o.strip() for o in str(self.CORS_ORIGINS).split(",") if o.strip()]


settings = Settings()
