"""Application configuration for Farmacia Lumen BI backend."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_title: str = "Farmacia Lumen BI & Operations API"
    app_version: str = "1.0.0"
    db_path: Path = ROOT_DIR / "data" / "farmacia.db"
    default_start_date: str = "2025-05-01"
    default_end_date: str = "2026-10-31"
    currency_label: str = "RON (fără TVA)"
    warm_cache_on_startup: bool = True
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Headless AI Analyst settings (loaded from .env; never logged)
    analyst_provider: str = "gemini_api"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_cli_bin: str = "gemini"
    claude_cli_bin: str = "claude"
    analyst_max_rows: int = 200
    analyst_query_timeout_sec: float = 10.0


settings = Settings()
