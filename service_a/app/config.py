from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    port: int = 8000
    client_api_key: str = "test_client_key"
    internal_api_key: str = "test_internal_key"
    service_b_url: str = "http://localhost:8001"
    
    # We ignore extra environment variables to prevent initialization errors
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
