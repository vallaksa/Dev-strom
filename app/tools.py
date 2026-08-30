"""Tavily web search fallback for idea generation.

Primary web context comes from Perplexity Sonar via OpenRouter
(`app.services.web_context`). This module is only invoked when Sonar fails
and `TAVILY_API_KEY` is configured.
"""

from langchain_core.tools import tool
from tavily import TavilyClient

from app.config import settings

MAX_RESULTS = 5
MAX_CHARS = 3_000


def _get_client() -> TavilyClient:
    api_key = settings.tavily_api_key
    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set in the environment")
    return TavilyClient(api_key=api_key)


def _search(query: str, char_budget: int = MAX_CHARS) -> str:
    results = _get_client().search(query=query, max_results=MAX_RESULTS).get("results", [])
    parts: list[str] = []
    used = 0
    for r in results:
        block = f"**{r.get('title', '')}**\n{r.get('content', '')}".strip()
        remaining = char_budget - used - len(parts)
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining]
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


@tool
def web_search_project_ideas(tech_stack: str) -> str:
    """Search the web for project ideas and tutorials related to a tech stack.

    Tavily fallback only — Sonar (`fetch_real_world_problems`) is the primary path.
    """
    query = f"project ideas and tutorials for {tech_stack}"
    return _search(query)
