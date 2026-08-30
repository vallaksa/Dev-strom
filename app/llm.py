"""OpenRouter LLM client and switchable model list.

`config/llm.json` is the source of truth for which models are available.
Change `active` (or set DEVSTROM_MODEL) to switch. UUID/API keys stay in .env.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from langchain_openai import ChatOpenAI

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "llm.json"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def load_llm_config(path: Path | None = None) -> dict:
    cfg_path = path or DEFAULT_CONFIG_PATH
    with cfg_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    models = list(data.get("models") or [])
    if not models:
        raise ValueError(f"{cfg_path} must list at least one model in 'models'.")
    active = data.get("active") or models[0]
    return {
        "provider": data.get("provider") or "openrouter",
        "base_url": data.get("base_url") or DEFAULT_BASE_URL,
        "active": active,
        "models": models,
    }


def model_chain(cfg: dict | None = None, *, active: str | None = None) -> tuple[str, list[str]]:
    cfg = cfg or load_llm_config()
    models = list(cfg["models"])
    chosen = active or cfg["active"]
    if chosen not in models:
        models = [chosen, *models]
    fallbacks = [m for m in models if m != chosen]
    return chosen, fallbacks


@lru_cache(maxsize=None)
def chat_model(model: str, api_key: str | None = None, base_url: str | None = None) -> ChatOpenAI:
    """OpenAI-compatible ChatOpenAI pointed at OpenRouter (or a test override)."""
    from app.config import settings

    key = api_key if api_key is not None else settings.api_key
    url = base_url or load_llm_config()["base_url"]
    return ChatOpenAI(
        model=model,
        api_key=key or "missing-api-key",
        base_url=url,
        temperature=0,
        default_headers={
            "HTTP-Referer": "https://github.com/vallaksa/Dev-Strom",
            "X-Title": "Dev-Strom",
        },
    )
