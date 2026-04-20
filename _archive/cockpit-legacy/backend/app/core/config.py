"""Application configuration via environment variables."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_env: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lanecore"

    # Claude API
    anthropic_api_key: str  # required — fails fast if missing

    @model_validator(mode="after")
    def _load_api_key_from_dotenv_if_empty(self) -> "Settings":
        """If ANTHROPIC_API_KEY env var is empty, load from .env file directly."""
        if not self.anthropic_api_key:
            # pydantic-settings ignores .env when env var is set (even if empty)
            # So we manually load it
            from dotenv import dotenv_values
            for env_path in [".env", "backend/.env"]:
                if os.path.exists(env_path):
                    vals = dotenv_values(env_path)
                    key = vals.get("ANTHROPIC_API_KEY", "")
                    if key:
                        self.anthropic_api_key = key
                        break
        return self
    claude_model_complex: str = "claude-opus-4-6"    # Für komplexe Baupläne
    claude_model_simple: str = "claude-sonnet-4-6"   # Für Vorverarbeitung

    # Storage (S3)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-central-1"
    s3_bucket_name: str = "lanecore-uploads"

    # Auth (Clerk)
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3456",
        "http://localhost:4321",
        "https://frontend-lanecore-ai.vercel.app",
        "https://lanecore-ai.vercel.app",
    ]

    # Limits
    max_pdf_size_mb: int = 50
    max_pages_per_plan: int = 200


settings = Settings()  # type: ignore[call-arg]
