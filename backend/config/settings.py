from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://docforge:docforge@localhost:5432/docforge"
    redis_url: str = "redis://localhost:6379/0"
    storage_provider: str = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "docforge"
    minio_secret_key: str = "docforge123"
    minio_bucket: str = "docforge"
    minio_use_ssl: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    log_level: str = "INFO"
    otel_service_name: str = "docforge"
    enable_otel: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
