"""Shared Streamlit UI components.

Extracted from ui.py so that both the Home page and History page
can render idea cards with the same layout.
"""

import streamlit as st
import streamlit.components.v1 as components

import ui.api_client as api


def idea_dict(idea) -> dict:
    """Normalize an idea to a plain dict regardless of source type."""
    return idea if isinstance(idea, dict) else (
        idea.model_dump() if hasattr(idea, "model_dump") else {}
    )


def render_idea_card(
    idea: dict,
    index: int,
    run_id: str,
    *,
    read_only: bool = False,
) -> None:
    """Render a single idea as an expandable Streamlit card.

    Args:
        idea: The idea dict with keys: name, problem_statement, why_it_fits,
              real_world_value, implementation_plan, pid.
        index: 1-based display index.
        run_id: The parent run's UUID string.
        read_only: If True, hides Expand/Export buttons (used in History view).
    """
    d = idea_dict(idea)
    pid = d.get("pid", index)
    name = (d.get("name") or "").strip() or "Idea"

    with st.expander(f"{index}. {name}", expanded=True):
        # Problem statement
        problem = (d.get("problem_statement") or "").strip()
        st.markdown("**Problem**")
        st.write(problem if problem else "_Could not generate. Try again._")

        # Why it fits
        fits = d.get("why_it_fits") or []
        if fits:
            st.markdown("**Why it fits**")
            st.markdown("\n".join(f"- {b}" for b in fits))

        # Real-world value
        st.markdown("**Real-world value**")
        real = (d.get("real_world_value") or "").strip()
        st.write(real if real else "_Could not generate. Try again._")

        # Implementation plan
        steps = d.get("implementation_plan") or []
        if steps:
            st.markdown("**Implementation plan**")
            for j, step in enumerate(steps, 1):
                st.write(f"{j}. {step}")

        if read_only:
            return

        # ── Expand ────────────────────────────────────────────────────
        expand_key = f"expanded_{run_id}_{index}"
        if st.button("Expand idea", key=f"expand_{run_id}_{index}"):
            with st.spinner("Generating deeper plan…"):
                try:
                    expanded = api.expand_idea(run_id, pid)
                except Exception as exc:
                    st.error(f"Expand failed: {exc}")
                    expanded = None
            if expanded:
                st.session_state[expand_key] = expanded
                st.rerun()

        expanded_data = st.session_state.get(expand_key)
        if expanded_data:
            ext = expanded_data.get("extended_plan") or []
            if ext:
                st.markdown("**Extended plan**")
                for j, step in enumerate(ext, 1):
                    st.write(f"{j}. {step}")
            else:
                st.warning("Could not generate extended plan.")

            # ── Export ────────────────────────────────────────────────
            try:
                md = api.export_idea(run_id, pid)
            except Exception:
                from app.services.export_formatter import idea_to_markdown
                tech = st.session_state.get("export_tech_stack", "")
                md = idea_to_markdown(d, ext, tech or None)

            fname = (name.replace(" ", "_")[:50] or "idea") + ".md"
            st.download_button(
                "Download as Markdown",
                data=md,
                file_name=fname,
                mime="text/markdown",
                key=f"download_{run_id}_{index}",
            )


# ── Project Cartographer (F1) ────────────────────────────────────────────────

def render_mermaid(diagram: str, *, height: int = 520) -> None:
    """Render a Mermaid diagram string client-side.

    `st.markdown()` does not render mermaid code fences, so this embeds a
    small self-contained HTML snippet (via `st.components.v1.html`) that
    loads mermaid.js from a CDN and renders `diagram` in the browser.
    """
    if not diagram or not diagram.strip():
        st.info("No architecture diagram was generated for this run.")
        return

    html = f"""
    <div class="mermaid">
{diagram}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
    </script>
    """
    components.html(html, height=height, scrolling=True)
