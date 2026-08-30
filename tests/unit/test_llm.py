"""LLM routing config: OpenRouter + switchable model list."""

from pathlib import Path

from app.llm import chat_model, load_llm_config, model_chain

_CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "llm.json"


def test_llm_config_lists_requested_models():
    cfg = load_llm_config(_CONFIG)
    assert cfg["provider"] == "openrouter"
    assert cfg["base_url"] == "https://openrouter.ai/api/v1"
    assert cfg["active"] in cfg["models"]
    assert "z-ai/glm-5.3-flash" in cfg["models"]
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in cfg["models"]


def test_model_chain_active_first_then_the_rest():
    cfg = {
        "active": "z-ai/glm-5.3-flash",
        "models": [
            "z-ai/glm-5.3-flash",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ],
    }
    primary, fallbacks = model_chain(cfg)
    assert primary == "z-ai/glm-5.3-flash"
    assert fallbacks == ["nvidia/nemotron-3-ultra-550b-a55b:free"]


def test_model_chain_env_override_moves_active():
    cfg = {
        "active": "z-ai/glm-5.3-flash",
        "models": [
            "z-ai/glm-5.3-flash",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ],
    }
    primary, fallbacks = model_chain(cfg, active="nvidia/nemotron-3-ultra-550b-a55b:free")
    assert primary == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert fallbacks == ["z-ai/glm-5.3-flash"]


def test_chat_model_targets_openrouter(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    llm = chat_model("z-ai/glm-5.3-flash", api_key="test-api-key")
    model_id = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    assert model_id == "z-ai/glm-5.3-flash"
    base = str(getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", "") or "")
    assert "openrouter.ai" in base
