from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables
    and an optional .env file.
    """

    # API key for protecting endpoints (optional; leave empty to disable auth)
    # L-6: Field was missing — getattr fallback in security.py always returned ""
    # meaning auth was permanently disabled even when API_KEY was set in .env.
    api_key: str = Field(default="")

    # Application
    app_name: str = "Fact Knowledge Layer"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fact_layer"
    postgres_user: str = "fact_user"
    postgres_password: str = "fact_password"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # LLM Provider
    # Current default: Ollama running locally.
    llm_provider: str = "ollama"

    # Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"

    # OpenAI - optional provider
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # Gemini - optional provider
    gemini_api_key: str = Field(default="")
    gemini_model: str = "gemini-2.0-flash"  # H-4: was "gemini-3.6-flash" (non-existent)

    # File storage
    upload_dir: str = "./storage/uploads"
    max_upload_size_mb: int = 50

    # Vector embeddings
    # H-5: Dimension must match the embedding model in use.
    # Ollama models typically produce 768 or 1024 dims, not 1536 (OpenAI).
    # Override with EMBEDDING_DIM in .env when switching models.
    embedding_dim: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """PostgreSQL connection URL for SQLAlchemy."""
        return (
            f"postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL."""
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """Celery result backend URL."""
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached application settings instance.

    Caching prevents repeatedly parsing environment variables
    throughout the application lifecycle.
    """
    return Settings()


settings = get_settings()
