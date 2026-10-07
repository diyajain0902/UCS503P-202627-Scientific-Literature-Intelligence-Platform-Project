"""Environment-based application settings."""

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings read from ``SLIP_``-prefixed environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="SLIP_", env_file=".env", extra="ignore")

    environment: str = Field(default="development", pattern="^(development|test|production)$")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:3b", min_length=1)
    ollama_timeout_seconds: float = Field(default=60.0, gt=0, le=600)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
