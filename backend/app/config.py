import os
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "ChronicleAI API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server Binding
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Storage & Database
    DATA_DIR: Path = BACKEND_DIR / "data"
    UPLOAD_DIR: Path = BACKEND_DIR / "data" / "files"
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR.as_posix()}/data/chronicle.db"
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt", "csv", "json", "log"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Optional AI Config (for Phase 2+)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached instance of application settings."""
    settings = Settings()
    # Ensure runtime data directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return settings
