from functools import lru_cache
import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Render/Neon often provide postgres://; SQLAlchemy async needs postgresql+asyncpg://."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    # asyncpg does not accept libpq sslmode query params the same way; strip them.
    # SSL is enabled separately in the engine for non-local hosts.
    for key in ("sslmode", "channel_binding"):
        url = re.sub(rf"([?&]){key}=[^&]*&?", r"\1", url)
    url = url.rstrip("?&")
    return url


def database_needs_ssl(url: str) -> bool:
    lower = url.lower()
    if "localhost" in lower or "127.0.0.1" in lower:
        return False
    return True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "CourierGuider"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/logistics_ai"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: object) -> object:
        if isinstance(v, str) and v:
            return _normalize_database_url(v)
        return v

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    llm_provider: str = "xai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.x.ai/v1"
    llm_model: str = "grok-4.6"
    llm_max_retries: int = 2
    llm_retry_base_seconds: float = 1.0
    llm_retry_max_seconds: float = 8.0

    embedding_provider: str = "openai_compatible"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    object_storage_provider: str = "local"
    object_storage_bucket: str = "uploads"
    object_storage_local_path: str = "./storage"

    cors_origins: str = "http://localhost:3000"

    max_upload_mb: int = 25
    rag_top_k: int = 20
    rag_final_k: int = 5

    realtime_data_max_age_seconds: int = 300
    tracking_max_age_seconds: int = 300
    quote_max_age_seconds: int = 300
    availability_max_age_seconds: int = 1800

    courier_guider_prompt_version: str = "courier_guider_v2"

    web_search_provider: str = "mock"
    tavily_api_key: str = ""
    tavily_search_depth: str = "basic"
    tavily_max_results: int = 5
    web_search_cache_hours: int = 6
    rag_stale_days: int = 90

    # Official-source-first live search (per-carrier Tavily)
    official_search_timeout_seconds: float = 8.0
    official_search_max_results: int = 4
    official_search_depth: str = "advanced"
    official_min_usable_hits: int = 2
    live_search_result_cap: int = 12

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
