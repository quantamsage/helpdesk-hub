"""Settings, read once from environment variables.

The app refuses to start if something required is missing or unsafe,
so mistakes show up at deploy time instead of as strange bugs later.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when an environment variable is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    access_token_minutes: int
    cors_origins: list[str]
    environment: str  # "development" or "production"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_settings() -> Settings:
    load_dotenv()  # reads backend/.env locally; does nothing on Render

    jwt_secret = _required("JWT_SECRET")
    if len(jwt_secret) < 32:
        raise ConfigError("JWT_SECRET must be at least 32 characters long.")

    environment = os.getenv("ENVIRONMENT", "development")
    if environment not in ("development", "production"):
        raise ConfigError("ENVIRONMENT must be 'development' or 'production'.")

    return Settings(
        database_url=_required("DATABASE_URL"),
        jwt_secret=jwt_secret,
        access_token_minutes=_token_minutes(),
        cors_origins=parse_cors_origins(os.getenv("CORS_ORIGINS", "")),
        environment=environment,
    )


def parse_cors_origins(raw: str) -> list[str]:
    """Turn "https://a.com, http://localhost:3000" into a clean list."""
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ConfigError("CORS_ORIGINS must list exact URLs, never '*'.")
    return origins


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _token_minutes() -> int:
    raw = os.getenv("ACCESS_TOKEN_MINUTES", "30")
    if not raw.isdigit() or not 1 <= int(raw) <= 1440:
        raise ConfigError("ACCESS_TOKEN_MINUTES must be a whole number from 1 to 1440.")
    return int(raw)
