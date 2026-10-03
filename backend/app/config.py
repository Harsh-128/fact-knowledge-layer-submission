from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables
    and an optional .env file.

    Railway deployment injects DATABASE_URL and REDIS_URL as single
    connection strings. Those take priority over the individual
    host/port/user/password fields when present.
    """

    # API key for protecting endpoints (optional; leave empty to disable auth)
    api_key: str = Field(default="")

    # Application
    app_name: str = "Fact Knowledge Layer"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Database — individual fields (local dev)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fact_layer"
    postgres_user: str = "fact_user"
    postgres_password: str = "fact_password"

    # Database — Railway / cloud single URL (takes priority when set)
    database_url: str = Field(default="")

    # Redis — individual fields (local dev)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Redis — Railway / cloud single URL (takes priority when set)
    redis_url: str = Field(default="")

    # LLM Provider
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
    gemini_model: str = "gemini-3.5-flash-lite"

    # File storage
    upload_dir: str = "./storage/uploads"
    max_upload_size_mb: int = 50

    # Vector embeddings
    embedding_dim: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_database_url(self) -> str:
        """
        Return the SQLAlchemy-compatible PostgreSQL connection URL.

        Railway injects DATABASE_URL as a postgres:// or postgresql://
        URL. SQLAlchemy requires the psycopg3 driver prefix
        (postgresql+psycopg://). This method normalises both forms.
        """
        # 1. Prefer the single DATABASE_URL env var (Railway / cloud).
        raw = self.database_url or os.environ.get("DATABASE_URL", "")

        if raw:
            # Replace any of the common prefixes with the psycopg3 driver prefix.
            for prefix in (
                "postgresql+psycopg2://",
                "postgresql+psycopg://",
                "postgresql://",
                "postgres://",
            ):
                if raw.startswith(prefix):
                    return "postgresql+psycopg://" + raw[len(prefix):]
            return raw

        # 2. Fall back to individual host/port/user/password fields (local dev).
        return (
            f"postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    def get_redis_url(self) -> str:
        """
        Return the Redis connection URL.

        Railway injects REDIS_URL as a redis:// URL. This method
        returns that directly, or falls back to the individual fields.
        """
        raw = self.redis_url or os.environ.get("REDIS_URL", "")
        if raw:
            return raw
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL."""
        return self.get_redis_url()

    @property
    def celery_result_backend(self) -> str:
        """Celery result backend URL."""
        return self.get_redis_url()


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached application settings instance.
    """
    return Settings()


settings = get_settings()
