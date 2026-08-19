import json
import re
from functools import lru_cache
from typing import TypedDict

from deepagents import create_deep_agent
from langgraph.graph import END, START, StateGraph

from app.models.domain import ProjectIdea
from app.services.mcp_client import is_mcp_enabled, load_mcp_tools
from app.services.models import ANONYMOUS_USER_ID
from app.tools import web_search_project_ideas


# ── Model constant ────────────────────────────────────────────────────────
MODEL = "gpt-5-mini"

# ── state ─────────────────────────────────────────────────────────────────────

class DevStromStateRequired(TypedDict):
    tech_stack: str
    web_context: str
    ideas: list[dict]


class DevStromStateOptional(TypedDict, total=False):
    domain: str
    level: str
    enable_multi_query: bool
    count: int


class DevStromState(DevStromStateRequired, DevStromStateOptional):
    pass


# ── shared helpers ────────────────────────────────────────────────────────────

# Anchored to string start/end only (no re.MULTILINE — that would match mid-JSON newlines)
_FENCE_RE_START = re.compile(r"\A```(?:json)?\s*")
_FENCE_RE_END = re.compile(r"\s*```\Z")


def _strip_markdown_fences(text: str) -> str:
    """Remove optional ``` / ```json fences that some models wrap JSON in."""
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE_START.sub("", text, count=1)
        text = _FENCE_RE_END.sub("", text, count=1)
    return text.strip()


def _extract_last_content(result: dict) -> str:
    """Pull the string content from the last message in an agent result."""
    messages = result.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    return last.content if hasattr(last, "content") else str(last)


# ── agent singletons (created once, reused) ───────────────────────────────────

@lru_cache(maxsize=2)
def _get_idea_agent(use_mcp: bool):
    tools = list(load_mcp_tools()) if use_mcp else []
    prompt = _IDEAS_SYSTEM_MCP if use_mcp else _IDEAS_SYSTEM
    return create_deep_agent(
        name="idea_generator",
        model=MODEL,
        tools=tools,
        system_prompt=prompt,
    )


@lru_cache(maxsize=None)
def _get_expand_agent():
    return create_deep_agent(
        name="expand_idea",
        model=MODEL,
        tools=[],
        system_prompt=_EXPAND_SYSTEM,
    )


# ── system prompts ────────────────────────────────────────────────────────────

_IDEAS_SYSTEM = """\
You are a strictly-controlled project-idea generator for developers learning a tech stack.

Follow these instructions exactly and obey all guardrails:

1. Output MUST be valid JSON, using ONLY the exact shape below. Do NOT include markdown code fences, explanations, headings, or any extra text.
2. Generate exactly N concrete project ideas (N is given in the user message). No more, no less.
3. Use THIS JSON shape, and nothing else:
{
  "ideas": [
    {
      "name": "Project Title",
      "problem_statement": "Clear, 1-2 sentence definition of the business problem.",
      "why_it_fits": [
        "Tech Name: Specific reason why this tech is the industry standard for this problem.",
        "Tech Name: Another specific reason..."
      ],
      "real_world_value": "One sentence on the business impact (e.g. revenue, efficiency, risk).",
      "implementation_plan": [
        "Step 1: Architect/Setup...",
        "Step 2: Core Logic...",
        "Step 3: Integration/Polish..."
      ]
    }
  ]
}

4. CONTENT GUIDELINES:
   - "name": Short, professional project title.
   - "problem_statement": 1–2 sentences describing what problem the project solves.
   - "why_it_fits": Each string MUST start with the Tech Name followed by a colon. Do not list generic benefits; link the tech to the specific domain problem. Aim for one bullet per key tech.
   - "real_world_value": Focus on business value (cost, speed, accuracy, risk), not just coding practice.
   - "implementation_plan": 3–5 high-level, actionable steps that a developer could realistically follow.

5. DOMAIN BIAS:
   - If a Domain/Company is provided (e.g. Walmart, Fintech), use terminology and architectural patterns specific to that industry (e.g. "SCD Type 2" for data warehousing, "circuit breakers" for microservices).
   - Do NOT invent specific internal tool names for companies. Use industry-standard equivalents instead (e.g. use "S3" instead of "Walmart Object Store").

6. LEVEL CALIBRATION:
   - If Level = "Beginner": Focus on core language syntax, simple data modeling, CLI/File I/O, and single-service apps. Avoid complex distributed systems.
   - If Level = "Intermediate": Focus on common frameworks (Spring, Django, React, etc.), databases, and simple APIs.
   - If Level = "Advanced" / "Architect": Focus on distributed systems patterns (CAP theorem, event sourcing, caching strategies, idempotency), scalability, reliability, and fault tolerance.

7. DISTINCT IDEAS:
   - All N ideas must be meaningfully different from each other (different core problem, architecture, or primary focus), even when using the same tech stack and domain.

8. STRICT GUARDRAILS:
   - NO markdown, code blocks, comments, or text before/after/beside the JSON.
   - Do NOT use any tools or external APIs.
   - Do NOT invent new fields or deviate from the required JSON structure.
   - If the user misspells a technology, silently map it to the standard name (e.g. "ReactJS" -> "React") and use the corrected name in the output.
   - If you cannot comply with all instructions, output exactly: {"ideas": []}

9. HALLUCINATION CHECK:
   - Do NOT suggest technologies that do not exist (e.g. "Apache Wifi").
   - Ensure each "problem_statement" describes a solvable engineering problem, not a physical impossibility.
"""

_IDEAS_SYSTEM_MCP = _IDEAS_SYSTEM.replace(
    "   - Do NOT use any tools or external APIs.\n",
    "   - Use the provided MCP database tools to query past runs before generating ideas.\n",
) + """\
10. MCP DEDUPLICATION (required when database tools are available):
   - The user message includes `user_id` and `tech_stack`.
   - Before writing JSON, call the `query` tool to fetch the last 3 runs for this user and tech stack from the `runs` table (column `ideas` is JSONB).
   - Review past idea names and problem statements; ensure every new idea differs meaningfully in problem, architecture, or primary focus.
   - Example SQL:
     SELECT ideas, created_at FROM runs
     WHERE user_id = '<user_id>' AND tech_stack ILIKE '%<tech_stack>%'
     ORDER BY created_at DESC LIMIT 3
"""

_EXPAND_SYSTEM = """\
You are an implementation advisor. Given a project idea (name, problem_statement, implementation_plan), \
expand it into exactly 5 concise, actionable next steps a developer can follow.

Rules:
- Output valid JSON only, no markdown fences or extra text.
- Each step must be ONE sentence (max 30 words). Be specific and technical.
- Use this exact shape: {"extended_plan": ["Step 1: ...", "Step 2: ...", "Step 3: ...", "Step 4: ...", "Step 5: ..."]}
"""

_EMPTY_IDEA: dict = {
    "name": "",
    "problem_statement": "",
    "why_it_fits": [],
    "real_world_value": "",
    "implementation_plan": [],
}


# ── graph nodes ───────────────────────────────────────────────────────────────

def fetch_web_context(state: DevStromState) -> dict:
    result = web_search_project_ideas.invoke({
        "tech_stack": state["tech_stack"],
        "enable_multi_query": state.get("enable_multi_query", False),
        "domain": state.get("domain"),
    })
    return {"web_context": result or ""}


def _parse_ideas(raw: str, expected_count: int) -> list[dict]:
    """Parse and validate the LLM JSON response into a list of idea dicts."""
    raw = _strip_markdown_fences(raw)
    try:
        data = json.loads(raw)
        ideas = data.get("ideas", [])
        validated = [ProjectIdea.model_validate(i).model_dump() for i in ideas]
        return validated  # may be shorter/longer than expected_count; caller decides
    except Exception:
        return []


def generate_ideas(state: DevStromState) -> dict:
    tech_stack = state["tech_stack"]
    web_context = state["web_context"]
    count = max(1, min(5, state.get("count", 3)))

    parts = [
        f"Tech stack: {tech_stack}",
        f"user_id: {ANONYMOUS_USER_ID}",
    ]
    if domain := state.get("domain"):
        parts.append(f"Domain (bias ideas toward): {domain}")
    if level := state.get("level"):
        parts.append(f"Level (bias ideas toward): {level}")
    parts.append(f"\nWeb context:\n{web_context[:4000]}\n\nOutput exactly {count} ideas as JSON:\n")

    use_mcp = is_mcp_enabled()
    result = _get_idea_agent(use_mcp).invoke({
        "messages": [{"role": "user", "content": "\n".join(parts)}],
    })

    ideas = _parse_ideas(_extract_last_content(result), count)
    if not ideas:
        ideas = [_EMPTY_IDEA.copy() for _ in range(count)]

    return {"ideas": ideas}


# ── standalone utility (not part of the compiled graph) ──────────────────────

def expand_idea(idea: dict) -> dict:
    """Expand a single project idea into a deeper implementation plan."""
    # Option A: strip fields the expand agent doesn't need to reduce input tokens
    trimmed = {
        k: idea[k] for k in ("name", "problem_statement", "implementation_plan")
        if k in idea
    }
    user_content = f"Expand this project idea:\n{json.dumps(trimmed)}"
    result = _get_expand_agent().invoke({
        "messages": [{"role": "user", "content": user_content}],
    })

    content = _strip_markdown_fences(_extract_last_content(result))
    try:
        data = json.loads(content)
        steps = data.get("extended_plan", [])
        if isinstance(steps, list):
            return {"idea": idea, "extended_plan": [str(s) for s in steps]}
    except Exception:
        pass
    return {"idea": idea, "extended_plan": []}


# ── graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(DevStromState)
    graph.add_node("fetch_web_context", fetch_web_context)
    graph.add_node("generate_ideas", generate_ideas)
    graph.add_edge(START, "fetch_web_context")
    graph.add_edge("fetch_web_context", "generate_ideas")
    graph.add_edge("generate_ideas", END)
    return graph.compile()


app = build_graph()
