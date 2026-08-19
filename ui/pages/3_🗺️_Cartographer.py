"""Project Cartographer page — map a repository's architecture.

Calls POST /cartograph (repo_url or local path) and GET /cartograph/{run_id}
via api_client, then renders the resulting ArchitectureReport (summary,
components, layers, data flow, external integrations, a Mermaid diagram)
plus a raw node/edge explorer over the ProjectGraph.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for sub-page imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import ui.api_client as api
from ui.components import render_mermaid

st.set_page_config(page_title="Dev-Strom — Cartographer", page_icon="🗺️")
st.title("🗺️ Project Cartographer")
st.caption("Map a repository's architecture: components, layers, data flow, and a diagram")

# ── Input ─────────────────────────────────────────────────────────────────────

source = st.text_input(
    "Repository URL or local path",
    placeholder="e.g. https://github.com/org/repo or /path/to/local/repo",
    help="A git URL (https://... or git@...) is sent as repo_url; anything else is sent as a local path.",
)

col1, col2 = st.columns([1, 3])
with col1:
    run_clicked = st.button("Map architecture", type="primary")
with col2:
    run_id_lookup = st.text_input(
        "…or load a previous run by ID",
        placeholder="run_id",
        label_visibility="visible",
    )
    load_clicked = st.button("Load run")

if run_clicked:
    value = source.strip()
    if not value:
        st.warning("Enter a repository URL or local path")
        st.stop()

    is_url = value.startswith(("http://", "https://", "git@"))
    with st.spinner("Cloning/parsing the repo and analyzing its architecture… this can take a while."):
        try:
            if is_url:
                result = api.post_cartograph(repo_url=value)
            else:
                result = api.post_cartograph(path=value)
        except Exception as exc:
            st.error(f"Cartograph failed: {exc}")
            st.stop()

    st.session_state["cartograph_result"] = result

if load_clicked:
    rid = run_id_lookup.strip()
    if not rid:
        st.warning("Enter a run ID to load")
        st.stop()
    with st.spinner("Loading run…"):
        try:
            result = api.get_cartograph_run(rid)
        except Exception as exc:
            st.error(f"Failed to load run: {exc}")
            st.stop()
    st.session_state["cartograph_result"] = result

# ── Render ────────────────────────────────────────────────────────────────────

result = st.session_state.get("cartograph_result")

if not result:
    st.info("Enter a repo URL or local path above and click **Map architecture** to get started.")
    st.stop()

run_id = result.get("run_id", "")
project_graph = result.get("project_graph") or {}
report = result.get("architecture_report") or {}

st.success(f"Run ID: `{run_id}`")

# ── Summary ───────────────────────────────────────────────────────────────────

st.subheader("Summary")
st.write(report.get("summary") or "_No summary generated._")

# ── Layers ────────────────────────────────────────────────────────────────────

layers = report.get("layers") or []
if layers:
    st.subheader("Layers")
    st.markdown(" → ".join(f"`{layer}`" for layer in layers))

# ── Components ────────────────────────────────────────────────────────────────

components_list = report.get("components") or []
if components_list:
    st.subheader("Components")
    st.dataframe(
        [
            {
                "name": c.get("name", ""),
                "responsibility": c.get("responsibility", ""),
                "node_ids": ", ".join(c.get("node_ids") or []),
            }
            for c in components_list
        ],
        use_container_width=True,
        hide_index=True,
    )

# ── Data flow ─────────────────────────────────────────────────────────────────

data_flow = report.get("data_flow") or ""
if data_flow:
    st.subheader("Data flow")
    st.write(data_flow)

# ── External integrations ────────────────────────────────────────────────────

integrations = report.get("external_integrations") or []
if integrations:
    st.subheader("External integrations")
    st.markdown("\n".join(f"- {i}" for i in integrations))

# ── Diagram ───────────────────────────────────────────────────────────────────

st.subheader("Architecture diagram")
render_mermaid(report.get("mermaid") or "")

# ── Risks ─────────────────────────────────────────────────────────────────────

risks = report.get("risks") or []
if risks:
    st.subheader("Risks")
    st.markdown("\n".join(f"- {r}" for r in risks))

# ── Node / edge explorer ──────────────────────────────────────────────────────

with st.expander("Node / edge explorer", expanded=False):
    nodes = project_graph.get("nodes") or []
    edges = project_graph.get("edges") or []

    st.caption(
        f"{len(nodes)} node(s) · {len(edges)} edge(s) · "
        f"languages: {', '.join(project_graph.get('languages') or []) or 'n/a'}"
    )

    st.markdown("**Nodes**")
    if nodes:
        st.dataframe(
            [
                {
                    "id": n.get("id", ""),
                    "type": n.get("type", ""),
                    "label": n.get("label", ""),
                    "path": n.get("path", ""),
                    "language": n.get("language", ""),
                }
                for n in nodes
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("_No nodes._")

    st.markdown("**Edges**")
    if edges:
        st.dataframe(
            [
                {
                    "source": e.get("source", ""),
                    "target": e.get("target", ""),
                    "type": e.get("type", ""),
                }
                for e in edges
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("_No edges._")

    entrypoints = project_graph.get("entrypoints") or []
    if entrypoints:
        st.markdown("**Entrypoints**")
        st.markdown("\n".join(f"- `{e}`" for e in entrypoints))

    manifests = project_graph.get("manifests") or {}
    if manifests:
        st.markdown("**Manifests**")
        st.json(manifests)
