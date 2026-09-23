import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "EvidenceX Backend API"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    
    # Supabase / Database Credentials (From Environment Variables Only)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # Future Provider Placeholders (Phases 3-5)
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "tavily")
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    FACT_CHECK_PROVIDER: str = os.getenv("FACT_CHECK_PROVIDER", "google_factcheck")
    FACT_CHECK_API_KEY: str = os.getenv("FACT_CHECK_API_KEY", "")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
