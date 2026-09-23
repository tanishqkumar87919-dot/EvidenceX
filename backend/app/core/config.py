import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "EvidenceX Backend API"
    APP_ENV: str = "development"
    APP_URL: str = "http://localhost:8000"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # CORS (can be comma-separated string or list)
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000"
    
    # Supabase / Database Credentials (From Environment Variables Only)
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    # Future Provider Placeholders (Phases 3-5)
    SEARCH_PROVIDER: str = "tavily"
    SEARCH_API_KEY: str = ""
    FACT_CHECK_PROVIDER: str = "google_factcheck"
    FACT_CHECK_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [o.strip() for o in str(self.CORS_ORIGINS).split(",") if o.strip()]

settings = Settings()
