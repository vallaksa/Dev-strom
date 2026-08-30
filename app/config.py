"""
Typed application configuration.

Centralizes everything Dev-Strom reads from the environment / `.env` so that
importing `app` never crashes just because a variable is unset (see
`app/services/db.py` for the lazy-engine counterpart of this). Values are
loaded once into the module-level `settings` singleton; import and use that
instead of calling `os.getenv(...)` around the codebase.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm import load_llm_config, model_chain

_LLM_PRIMARY, _LLM_FALLBACKS = model_chain(load_llm_config())


class Settings(BaseSettings):
    """Environment-backed configuration. All fields are optional at import
    time — endpoints that need a given key (e.g. API_KEY) validate
    its presence themselves and return a 503 rather than crashing on import.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── provider keys ──────────────────────────────────────────────────────
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"),
    )
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")

    # ── database ───────────────────────────────────────────────────────────
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # ── graph database (F1-4, Neo4jStore) ─────────────────────────────────
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NEO4J_USER", "NEO4J_USERNAME"),
    )
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")

    # Which CartographStore backend to use: "postgres" (default) or "neo4j".
    cartograph_store_backend: str = Field(default="postgres", alias="CARTOGRAPH_STORE_BACKEND")

    # ── LLM model selection ────────────────────────────────────────────────
    # Defaults come from config/llm.json. Override with DEVSTROM_MODEL to
    # switch without editing the file. Remaining listed models are fallbacks.
    model: str = Field(default=_LLM_PRIMARY, alias="DEVSTROM_MODEL")
    model_fallbacks: list[str] = Field(
        default_factory=lambda: list(_LLM_FALLBACKS),
        alias="DEVSTROM_MODEL_FALLBACKS",
    )

    # ── service URLs ───────────────────────────────────────────────────────
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")

    # ── LangSmith tracing ──────────────────────────────────────────────────
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str | None = Field(default=None, alias="LANGCHAIN_ENDPOINT")
    langchain_api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str | None = Field(default=None, alias="LANGCHAIN_PROJECT")

    # ── logging ────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide `Settings` singleton (cached after first call)."""
    return Settings()


# Module-level singleton for convenient `from app.config import settings`.
settings = get_settings()
