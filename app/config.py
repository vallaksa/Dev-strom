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

from app.llm import load_llm_config, model_chain, search_model_name

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

    @property
    def openai_api_key(self) -> str | None:
        """Backward-compatible alias for api_key."""
        return self.api_key

    # ── database ───────────────────────────────────────────────────────────
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # ── LLM model selection ────────────────────────────────────────────────
    # Defaults come from config/llm.json. Override with DEVSTROM_MODEL to
    # switch without editing the file. Remaining listed models are fallbacks.
    model: str = Field(default=_LLM_PRIMARY, alias="DEVSTROM_MODEL")
    model_fallbacks: list[str] = Field(
        default_factory=lambda: list(_LLM_FALLBACKS),
        alias="DEVSTROM_MODEL_FALLBACKS",
    )
    search_model: str = Field(
        default_factory=lambda: search_model_name(load_llm_config()),
        alias="DEVSTROM_SEARCH_MODEL",
    )

    # ── service URLs ───────────────────────────────────────────────────────
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    # Where the browser is served from — used for OAuth redirects back into
    # the SPA after a successful login, and to decide whether the session
    # cookie should be marked Secure.
    web_base_url: str = Field(default="http://localhost:5173", alias="WEB_BASE_URL")

    # ── auth (V3-4+) ───────────────────────────────────────────────────────
    # When false, every request runs as the seeded anonymous user and no
    # login gate is enforced — the default so local dev works without OAuth
    # apps. Set true in any deployment that should require sign-in.
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    # HMAC secret for the JWT session cookie. Required when auth_enabled.
    session_secret: str | None = Field(default=None, alias="SESSION_SECRET")
    session_ttl_days: int = Field(default=7, alias="SESSION_TTL_DAYS")

    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    github_client_id: str | None = Field(default=None, alias="GITHUB_CLIENT_ID")
    github_client_secret: str | None = Field(default=None, alias="GITHUB_CLIENT_SECRET")

    @property
    def session_cookie_secure(self) -> bool:
        return self.web_base_url.startswith("https://")

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
