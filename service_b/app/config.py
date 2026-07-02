from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    port: int = 8001
    internal_api_key: str = "test_internal_key"
    cache_ttl_seconds: int = 300
    database_url: str = "sqlite:///market_cache.db"
    primary_provider: str = "yfinance"
    fallback_provider: str = "none"
    eodhd_api_key: Optional[str] = None
    
    # We ignore extra environment variables to prevent initialization errors
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
