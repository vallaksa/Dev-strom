"""Live web context for idea generation via Perplexity Sonar (OpenRouter)."""

from __future__ import annotations

import logging

from app.config import settings
from app.llm import chat_model
from app.tools import web_search_project_ideas

logger = logging.getLogger(__name__)

_SONAR_PROMPT = """\
Find exactly 2 distinct, current real-world problems or pain points relevant to this developer's intent:

{intent}

For each problem:
1. Name the problem clearly (what goes wrong in production or business today).
2. Explain why it matters now (recent trends, industry pressure, or technology shifts).
3. Note what kind of software project could address it.

Write as concise prose — two clearly separated sections. Do not include URLs or citation markers in the text.
"""


def fetch_real_world_problems(intent: str) -> str:
    """Fetch two real-world problems grounded in live web search (Sonar primary, Tavily fallback)."""
    intent = (intent or "").strip()
    if not intent:
        return ""

    sonar_text = _fetch_via_sonar(intent)
    if sonar_text:
        return sonar_text

    if settings.tavily_api_key:
        logger.warning("Sonar fetch failed; falling back to Tavily")
        try:
            return web_search_project_ideas.invoke({"tech_stack": intent}) or ""
        except Exception:
            logger.exception("Tavily fallback also failed")
    return ""


def _fetch_via_sonar(intent: str) -> str:
    if not settings.api_key:
        return ""

    model = settings.search_model
    try:
        llm = chat_model(model)
        response = llm.invoke(
            _SONAR_PROMPT.format(intent=intent),
            extra_body={"search_recency_filter": "month"},
        )
        content = response.content if hasattr(response, "content") else str(response)
        return (content or "").strip()
    except Exception:
        logger.exception("Sonar web context fetch failed for model %r", model)
        return ""
