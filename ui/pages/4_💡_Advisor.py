"""Improvement / Feature Advisor page — a prioritized roadmap grounded in
the actual code graph.

Calls POST /advise (repo_url, local path, or an existing cartograph run_id)
and GET /advise/{run_id} via api_client, then renders the resulting
AdvisorReport: summary, detected tech stack, recommendations grouped by
category with impact/effort badges, quick wins vs strategic bets, and each
recommendation's affected components.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for sub-page imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import ui.api_client as api

st.set_page_config(page_title="Dev-Strom — Advisor", page_icon="💡")
st.title("💡 Improvement / Feature Advisor")
st.caption(
    "A prioritized roadmap — next features, refactors, tech debt, and risks — "
    "grounded in the actual code graph."
)

# ── Input ─────────────────────────────────────────────────────────────────────
# Three ways in: a repo URL, a local path, or an existing cartograph run_id
# (skips the clone/parse/analyze step and advises against that run directly).

tab_repo, tab_run = st.tabs(["Map a repo", "Use an existing cartograph run"])

with tab_repo:
    source = st.text_input(
        "Repository URL or local path",
        placeholder="e.g. https://github.com/org/repo or /path/to/local/repo",
        help="A git URL (https://... or git@...) is sent as repo_url; anything else is sent as a local path.",
        key="advisor_source",
    )
    repo_clicked = st.button("Generate roadmap", type="primary", key="advisor_repo_button")

with tab_run:
    run_id_input = st.text_input(
        "Cartograph run ID",
        placeholder="run_id from a previous /cartograph run",
        key="advisor_run_id",
    )
    run_clicked = st.button("Generate roadmap from run", type="primary", key="advisor_run_button")

col1, col2 = st.columns([1, 3])
with col1:
    st.write("")
with col2:
    load_id = st.text_input("…or load a previous advisor run by ID", placeholder="run_id", key="advisor_load_id")
    load_clicked = st.button("Load run", key="advisor_load_button")

if repo_clicked:
    value = source.strip()
    if not value:
        st.warning("Enter a repository URL or local path")
        st.stop()

    is_url = value.startswith(("http://", "https://", "git@"))
    with st.spinner("Mapping the repo and building a prioritized roadmap… this can take a while."):
        try:
            if is_url:
                result = api.post_advise(repo_url=value)
            else:
                result = api.post_advise(path=value)
        except Exception as exc:
            st.error(f"Advisor failed: {exc}")
            st.stop()
    st.session_state["advisor_result"] = result

if run_clicked:
    rid = run_id_input.strip()
    if not rid:
        st.warning("Enter a cartograph run ID")
        st.stop()
    with st.spinner("Building a prioritized roadmap from this run…"):
        try:
            result = api.post_advise(run_id=rid)
        except Exception as exc:
            st.error(f"Advisor failed: {exc}")
            st.stop()
    st.session_state["advisor_result"] = result

if load_clicked:
    rid = load_id.strip()
    if not rid:
        st.warning("Enter an advisor run ID to load")
        st.stop()
    with st.spinner("Loading run…"):
        try:
            record = api.get_advise_run(rid)
        except Exception as exc:
            st.error(f"Failed to load run: {exc}")
            st.stop()
    # GET /advise/{run_id} returns {run_id, cartograph_run_id, repo_url,
    # advisor_report, created_at} — normalize to the same shape POST /advise
    # returns so rendering below is uniform.
    st.session_state["advisor_result"] = {
        "run_id": record.get("run_id", rid),
        "advisor_report": record.get("advisor_report") or {},
    }

# ── Render ────────────────────────────────────────────────────────────────────

result = st.session_state.get("advisor_result")

if not result:
    st.info(
        "Map a repo, point at an existing cartograph run, or load a previous advisor "
        "run above to get started."
    )
    st.stop()

run_id = result.get("run_id", "")
report = result.get("advisor_report") or {}

st.success(f"Run ID: `{run_id}`")

# ── Summary + tech stack ──────────────────────────────────────────────────────

st.subheader("Summary")
st.write(report.get("summary") or "_No summary generated._")

tech_stack = report.get("tech_stack") or []
if tech_stack:
    st.markdown("**Detected tech stack**")
    st.markdown(" ".join(f"`{t}`" for t in tech_stack))

recommendations = report.get("recommendations") or []

_IMPACT_BADGE = {"high": "🔴 high impact", "medium": "🟡 medium impact", "low": "⚪ low impact"}
_EFFORT_BADGE = {"high": "🏋️ high effort", "medium": "🚶 medium effort", "low": "⚡ low effort"}


def _render_recommendation(rec: dict) -> None:
    title = rec.get("title") or rec.get("id") or "Untitled recommendation"
    impact = rec.get("impact", "")
    effort = rec.get("effort", "")
    badges = " · ".join(
        b for b in (_IMPACT_BADGE.get(impact), _EFFORT_BADGE.get(effort)) if b
    )
    with st.expander(f"{title}", expanded=False):
        if badges:
            st.caption(badges)
        rationale = (rec.get("rationale") or "").strip()
        if rationale:
            st.markdown("**Rationale**")
            st.write(rationale)

        steps = rec.get("suggested_steps") or []
        if steps:
            st.markdown("**Suggested steps**")
            for j, step in enumerate(steps, 1):
                st.write(f"{j}. {step}")

        affected = rec.get("affected_node_ids") or []
        if affected:
            st.markdown("**Affected components**")
            st.markdown(", ".join(f"`{n}`" for n in affected))


# ── Quick wins vs strategic bets ──────────────────────────────────────────────

quick_wins = report.get("quick_wins") or []
strategic_bets = report.get("strategic_bets") or []

if quick_wins or strategic_bets:
    qcol, scol = st.columns(2)
    with qcol:
        st.subheader("⚡ Quick wins")
        if quick_wins:
            st.markdown("\n".join(f"- {w}" for w in quick_wins))
        else:
            st.write("_None identified._")
    with scol:
        st.subheader("🎯 Strategic bets")
        if strategic_bets:
            st.markdown("\n".join(f"- {b}" for b in strategic_bets))
        else:
            st.write("_None identified._")

# ── Recommendations, grouped by category ──────────────────────────────────────

st.subheader("Recommendations")

if not recommendations:
    st.write("_No recommendations generated._")
else:
    by_category: dict[str, list[dict]] = {}
    for rec in recommendations:
        by_category.setdefault(rec.get("category", "other"), []).append(rec)

    _CATEGORY_LABEL = {
        "feature": "🚀 Features",
        "refactor": "🛠️ Refactors",
        "tech_debt": "🧹 Tech debt",
        "risk": "⚠️ Risks",
        "test": "✅ Tests",
        "security": "🔒 Security",
        "performance": "⏱️ Performance",
        "docs": "📚 Docs",
    }

    for category, recs in by_category.items():
        st.markdown(f"#### {_CATEGORY_LABEL.get(category, category.title())}")
        for rec in recs:
            _render_recommendation(rec)
