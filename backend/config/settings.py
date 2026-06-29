from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://docforge:docforge@localhost:5432/docforge"
    redis_url: str = "redis://localhost:6379/0"
    storage_provider: str = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "docforge"
    minio_use_ssl: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    llm_provider: str = "openai"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    otel_service_name: str = "docforge"
    enable_otel: bool = False
    tesseract_cmd: str = "tesseract"
    # Local-first defaults: ollama nomic-embed-text (768) matches the pgvector
    # column dimension after migration 022. Using OpenAI (1536) requires migrating
    # the column back to vector(1536) and reindexing.
    embedding_provider: str = "ollama"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_embedding_model: str = "nomic-embed-text"
    # Single source of truth for the embedding vector size. MUST match the
    # pgvector column dimension (vector(768) in migration 022).
    embedding_dimension: int = 768


    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
