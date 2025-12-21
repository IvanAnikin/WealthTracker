"""Application configuration settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "WealthTracker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    
    # Database
    DATABASE_URL: str = "sqlite:///./wealth_tracker.db"
    
    # Open Banking Provider - TrueLayer
    TRUELAYER_CLIENT_ID: str = ""
    TRUELAYER_CLIENT_SECRET: str = ""
    TRUELAYER_BASE_URL: str = "https://api.truelayer.com"
    TRUELAYER_AUTH_URL: str = "https://auth.truelayer.com"
    
    # Open Banking Provider - GoCardless (Legacy)
    GOCARDLESS_SECRET_ID: str = ""
    GOCARDLESS_SECRET_KEY: str = ""
    GOCARDLESS_BASE_URL: str = "https://bankaccountdata.gocardless.com/api/v2"
    
    # Open Banking Provider - Tink
    TINK_CLIENT_ID: str = ""
    TINK_CLIENT_SECRET: str = ""
    TINK_API_URL: str = "https://api.tink.com"
    
    # Session
    SESSION_SECRET_KEY: str
    SESSION_COOKIE_NAME: str = "wealth_tracker_session"
    SESSION_MAX_AGE: int = 86400  # 24 hours
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8000"]
    
    # Sync Schedule
    SYNC_SCHEDULE_CRON: str = "0 */6 * * *"  # Every 6 hours
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
