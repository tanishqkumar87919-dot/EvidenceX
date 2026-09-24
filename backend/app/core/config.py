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
    GEMINI_API_KEY: str = ""

    # Web Search Provider (Phase 5)
    WEB_SEARCH_PROVIDER: str = "duckduckgo"  # options: duckduckgo, tavily, google, mock
    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_MAX_RESULTS: int = 5

    # Embedding Provider & RAG Vector Intelligence (Phase 5)
    EMBEDDING_PROVIDER: str = "gemini"  # options: gemini, openai, local, mock
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSIONS: int = 768
    EMBEDDING_API_KEY: str = ""
    RAG_CHUNK_SIZE: int = 600
    RAG_CHUNK_OVERLAP: int = 100
    RAG_TOP_K: int = 4
    RAG_SIMILARITY_THRESHOLD: float = 0.30

    # Verification Engine (Phase 6)
    VERIFICATION_PROVIDER: str = "gemini"  # options: gemini, openai, local, deterministic
    VERIFICATION_MODEL: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [o.strip() for o in str(self.CORS_ORIGINS).split(",") if o.strip()]


settings = Settings()
