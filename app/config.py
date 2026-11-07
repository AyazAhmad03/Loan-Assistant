"""
app/config.py — the app's single source of truth for settings.

Reads values from the .env file at the repo root. The .env file holds the
actual secrets (and is git-ignored); this file only declares which settings
exist and what type each must be.

Import everywhere as:  from app.config import settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read .env automatically; ignore other variables in it
    # (POSTGRES_USER, POSTGRES_PORT, ... are for Docker, not for us).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — required. If DATABASE_URL is missing from .env,
    # the app refuses to start with a clear error (fail fast).
    database_url: str

    # LLM — not used until Phase 5, so it defaults to empty.
    llm_api_key: str = ""


# One settings object, created once, shared by the whole app.
settings = Settings()