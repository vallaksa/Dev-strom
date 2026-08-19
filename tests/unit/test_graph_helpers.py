"""Unit tests for the pure-logic helpers in app/graph.py.

These exercise `_strip_markdown_fences` and `_parse_ideas` in isolation -
no LLM, no LangGraph invocation, no network calls. Importing app.graph
builds the (uncalled) compiled StateGraph at module load, which is a local
operation and does not touch the network.
"""

import json

from app.graph import _parse_ideas, _strip_markdown_fences

# ── _strip_markdown_fences ─────────────────────────────────────────────────


def test_strip_markdown_fences_plain_text_unchanged():
    text = '{"ideas": []}'
    assert _strip_markdown_fences(text) == text


def test_strip_markdown_fences_json_fenced():
    text = '```json\n{"ideas": []}\n```'
    assert _strip_markdown_fences(text) == '{"ideas": []}'


def test_strip_markdown_fences_plain_fenced():
    text = '```\n{"ideas": []}\n```'
    assert _strip_markdown_fences(text) == '{"ideas": []}'


def test_strip_markdown_fences_strips_surrounding_whitespace():
    text = '  \n```json\n{"ideas": []}\n```\n  '
    assert _strip_markdown_fences(text) == '{"ideas": []}'


def test_strip_markdown_fences_does_not_touch_inner_backticks():
    # Only the opening/closing fence should be stripped, not fences that
    # might appear (unexpectedly) inside the payload itself.
    inner = '{"ideas": [{"name": "uses `code` inline"}]}'
    text = f"```json\n{inner}\n```"
    assert _strip_markdown_fences(text) == inner


# ── _parse_ideas ────────────────────────────────────────────────────────────


def _valid_idea(n: int) -> dict:
    return {
        "name": f"Idea {n}",
        "problem_statement": f"Problem {n}",
        "why_it_fits": [f"Tech {n}: reason"],
        "real_world_value": f"Value {n}",
        "implementation_plan": [f"Step {n}"],
    }


def test_parse_ideas_valid_json():
    raw = json.dumps({"ideas": [_valid_idea(1), _valid_idea(2)]})
    result = _parse_ideas(raw, expected_count=2)
    assert len(result) == 2
    assert result[0]["name"] == "Idea 1"
    assert result[1]["name"] == "Idea 2"


def test_parse_ideas_fenced_json():
    raw = "```json\n" + json.dumps({"ideas": [_valid_idea(1)]}) + "\n```"
    result = _parse_ideas(raw, expected_count=1)
    assert len(result) == 1
    assert result[0]["name"] == "Idea 1"


def test_parse_ideas_garbage_returns_empty_list():
    assert _parse_ideas("not json at all {{{", expected_count=3) == []


def test_parse_ideas_empty_string_returns_empty_list():
    assert _parse_ideas("", expected_count=3) == []


def test_parse_ideas_missing_required_field_returns_empty_list():
    # Malformed idea (missing required ProjectIdea fields) fails pydantic
    # validation for the whole batch -> _parse_ideas swallows it and
    # returns [] rather than raising.
    bad_idea = {"name": "Incomplete"}
    raw = json.dumps({"ideas": [bad_idea]})
    assert _parse_ideas(raw, expected_count=1) == []


def test_parse_ideas_over_generation_returns_all_parsed():
    """The model returned 5 ideas though only 3 were requested; _parse_ideas
    itself does not truncate - that decision belongs to the caller."""
    raw = json.dumps({"ideas": [_valid_idea(i) for i in range(1, 6)]})
    result = _parse_ideas(raw, expected_count=3)
    assert len(result) == 5


def test_parse_ideas_under_generation_returns_all_parsed():
    """The model returned fewer ideas than requested; _parse_ideas returns
    what it got rather than padding or erroring."""
    raw = json.dumps({"ideas": [_valid_idea(1)]})
    result = _parse_ideas(raw, expected_count=3)
    assert len(result) == 1
