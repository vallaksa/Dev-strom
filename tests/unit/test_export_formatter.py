"""Unit tests for app/services/export_formatter.idea_to_markdown."""

from app.services.export_formatter import idea_to_markdown

FULL_IDEA = {
    "name": "Realtime Log Anomaly Detector",
    "problem_statement": "Ops teams miss early signs of incidents buried in noisy logs.",
    "why_it_fits": [
        "LangChain: orchestrates the multi-step detection pipeline.",
        "Postgres: durable storage for detected anomalies.",
    ],
    "real_world_value": "Cuts mean-time-to-detect for production incidents.",
    "implementation_plan": [
        "Step 1: Ingest logs from the message bus.",
        "Step 2: Score anomalies with a rolling baseline.",
    ],
}
FULL_EXTENDED_PLAN = [
    "Step 1: Stand up a Kafka consumer for the log topic.",
    "Step 2: Compute a z-score per log template.",
]


def test_idea_to_markdown_all_five_sections_present():
    md = idea_to_markdown(FULL_IDEA, FULL_EXTENDED_PLAN, tech_stack="Python, LangChain")

    assert "# Project: Realtime Log Anomaly Detector" in md
    assert "## 1. Context and goal" in md
    assert "## 2. High-level implementation plan" in md
    assert "## 3. Detailed implementation plan" in md
    assert "## 4. Assumptions / Out of scope" in md
    assert "## 5. Next step" in md


def test_idea_to_markdown_includes_content_fields():
    md = idea_to_markdown(FULL_IDEA, FULL_EXTENDED_PLAN, tech_stack="Python, LangChain")

    assert "Ops teams miss early signs" in md
    assert "Cuts mean-time-to-detect" in md
    assert "LangChain: orchestrates the multi-step detection pipeline." in md
    assert "1. Step 1: Ingest logs from the message bus." in md
    assert "1. Step 1: Stand up a Kafka consumer for the log topic." in md
    assert "**Tech stack:** Python, LangChain" in md


def test_idea_to_markdown_next_step_prefers_extended_plan_first_item():
    md = idea_to_markdown(FULL_IDEA, FULL_EXTENDED_PLAN, tech_stack="Python")
    assert "**Start with:** Step 1: Stand up a Kafka consumer for the log topic." in md


def test_idea_to_markdown_empty_fields_fall_back_to_not_specified():
    empty_idea = {
        "name": "",
        "problem_statement": "",
        "why_it_fits": [],
        "real_world_value": "",
        "implementation_plan": [],
    }

    md = idea_to_markdown(empty_idea, [], tech_stack=None)

    # Falls back to "Project" when name is blank.
    assert "# Project: Project" in md
    # Problem statement and real-world value fall back to "(Not specified)".
    assert md.count("(Not specified)") == 2
    # No tech-stack header line when tech_stack is None/falsy.
    assert "**Tech stack:**" not in md


def test_idea_to_markdown_next_step_falls_back_when_no_plans_at_all():
    empty_idea = {
        "name": "Empty",
        "problem_statement": "",
        "why_it_fits": [],
        "real_world_value": "",
        "implementation_plan": [],
    }
    md = idea_to_markdown(empty_idea, [], tech_stack=None)
    assert "**Start with:** Review the plan above and set up your environment." in md


def test_idea_to_markdown_next_step_falls_back_to_impl_plan_when_no_extended_plan():
    md = idea_to_markdown(FULL_IDEA, [], tech_stack=None)
    assert "**Start with:** Step 1: Ingest logs from the message bus." in md


def test_idea_to_markdown_ignores_blank_extended_plan_entries():
    md = idea_to_markdown(FULL_IDEA, ["", "   ", "Step 1: real step"], tech_stack=None)
    section_3 = md.split("## 3. Detailed implementation plan")[1].split("## 4.")[0]
    # Only the one non-blank entry should have made it through, as item "1.".
    assert "1. Step 1: real step" in section_3
    assert "2. " not in section_3
