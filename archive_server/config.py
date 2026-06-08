"""Environment-based settings for the archive server (VPS side)."""
import os
from dataclasses import dataclass


def _require(name: str, default: str = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Обязательная переменная окружения не задана: {name}")
    return value


@dataclass
class Settings:
    database_url: str
    media_root: str
    ingest_api_key: str
    session_secret: str
    control_base_url: str
    control_token: str
    cookie_secure: bool


def load_settings() -> Settings:
    return Settings(
        database_url=_require("DATABASE_URL", "sqlite:///./archive.db"),
        media_root=os.environ.get("MEDIA_ROOT", "./media"),
        ingest_api_key=_require("ARCHIVE_API_KEY"),
        session_secret=_require("SESSION_SECRET"),
        control_base_url=os.environ.get("CONTROL_BASE_URL", ""),
        control_token=os.environ.get("CONTROL_API_TOKEN", ""),
        cookie_secure=os.environ.get("COOKIE_SECURE", "true").lower() != "false",
    )


settings = load_settings()
