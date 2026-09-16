from functools import lru_cache
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import timedelta


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str
    environment: str
    debug: bool
    log_level: str

    api_v1_prefix: str

    database_url: str
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    sessionize_interval_seconds: int = 30

    cors_origins: Union[str, List[str]]

    secret_key: str
    algorithm: str
    access_token_expire_min: int
    refresh_token_expire_days: int
    enroll_token_expire_min: int = 30

    refresh_cookie_name: str = "attlytics_refresh"
    cookie_secure: bool | None = None
    refresh_cookie_samesite: str = "lax"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Allow CORS_ORIGINS to be a comma-separated string in .env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def refresh_cookie_secure(self) -> bool:
        """Secure unless explicitly set; automatically on in production."""
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"

    @property
    def refresh_cookie_path(self) -> str:
        return f"{self.api_v1_prefix.rstrip('/')}/auth"

    @property
    def api_root(self) -> str:
        return self.api_v1_prefix.rstrip("/").rsplit("/", 1)[0]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()

ACCESS_TOKEN_EXPIRE = timedelta(minutes=get_settings().access_token_expire_min)
REFRESH_TOKEN_EXPIRE = timedelta(days=get_settings().refresh_token_expire_days)
