"""
Application configuration using Pydantic Settings.
Supports environment variables and .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ───
    app_name: str = "Thesis Formatter API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # ─── API Server ───
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    # ─── Database ───
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/thesis_formatter"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ─── Redis ───
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = 3600  # 1 hour

    # ─── Celery ───
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # ─── MinIO (S3-compatible storage) ───
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="thesis-formatter")
    minio_secure: bool = False

    # ─── File Upload ───
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list[str] = Field(default=["docx", "pdf", "txt"])

    # ─── AI / LLM ───
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.1

    # ─── Task Processing ───
    task_timeout: int = 600  # 10 minutes
    task_max_retries: int = 3

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
