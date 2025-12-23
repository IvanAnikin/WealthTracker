"""Application configuration settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "WealthTracker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    
    # Database
    DATABASE_URL: str = "sqlite:///./wealth_tracker.db"
    
    # Open Banking Provider
    GOCARDLESS_SECRET_ID: str = ""
    GOCARDLESS_SECRET_KEY: str = ""
    GOCARDLESS_BASE_URL: str = "https://bankaccountdata.gocardless.com/api/v2"
    
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


settings = Settings()
