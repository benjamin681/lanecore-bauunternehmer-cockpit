"""Application configuration."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Backend-Root (= Ordner, in dem .env und pyproject.toml liegen)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Leere Shell-ENV-Variablen würden sonst .env-Werte überschreiben.
# Vor Settings-Init: entferne alle ENV-Vars, die leer sind, damit .env greift.
_env_file = _BACKEND_ROOT / ".env"
if _env_file.exists():
    # Lies .env und entferne leere shell-Overrides für Keys die in .env definiert sind
    try:
        from dotenv import dotenv_values as _dotenv_values

        for _k in _dotenv_values(_env_file).keys():
            if os.environ.get(_k) == "":
                os.environ.pop(_k, None)
    except ImportError:
        pass


class Settings(BaseSettings):
    """App-Settings — per Env-Variables überschreibbar."""

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Environment -------------------------------------------------------
    app_env: str = "development"
    app_name: str = "LV-Preisrechner"

    # --- Server ------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8100

    # --- Security ----------------------------------------------------------
    # In production: setze echten SECRET über ENV-Var!
    secret_key: str = "dev-insecure-change-in-production-please-please-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 Tage

    # --- Database ----------------------------------------------------------
    # In Produktion: DATABASE_URL per ENV (Postgres). Lokal: SQLite default.
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    sqlite_filename: str = "lv_preisrechner.db"

    @property
    def database_url(self) -> str:
        # Direkter ENV-Read statt pydantic-Alias (robuster in Produktion).
        override = os.environ.get("DATABASE_URL", "").strip()
        if override:
            # Render gibt postgres:// — SQLAlchemy erwartet postgresql://
            if override.startswith("postgres://"):
                override = override.replace("postgres://", "postgresql://", 1)
            return override
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / self.sqlite_filename}"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite:")

    @property
    def upload_dir(self) -> Path:
        p = self.data_dir / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # --- Anthropic ---------------------------------------------------------
    anthropic_api_key: str = ""
    claude_model_primary: str = "claude-sonnet-4-6"
    claude_model_fallback: str = "claude-opus-4-6"
    claude_max_tokens: int = 16000
    # Seiten pro Vision-Batch — kleiner = mehr Calls, aber saubereres JSON
    claude_pages_per_batch: int = 5

    # --- Parser-Prompt ------------------------------------------------------
    # Generischer Prompt (H/T/Z/E-Codes, Rabatt-Extraktion, Plausibilitaets-
    # Check) ist Default seit B+4.3. Bei Regression: auf False setzen und die
    # betroffenen Pricelists auf PENDING_PARSE zuruecksetzen + Re-Parse.
    use_generic_prompt: bool = True

    # --- CORS --------------------------------------------------------------
    # Aus ENV: JSON-Array `["https://foo.com"]` ODER Komma-Liste.
    cors_origins: list[str] = [
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://localhost:3000",  # Vercel lokal
    ]
    # Regex für Vercel-Preview-Deployments (*-lv-preisrechner.vercel.app)
    cors_origin_regex: str = r"https://.*\.vercel\.app"


settings = Settings()
