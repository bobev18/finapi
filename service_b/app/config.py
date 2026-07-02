from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    port: int = 8001
    internal_api_key: str = "test_internal_key"
    cache_ttl_seconds: int = 300
    database_url: str = "sqlite:///market_cache.db"
    
    # We ignore extra environment variables to prevent initialization errors
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
