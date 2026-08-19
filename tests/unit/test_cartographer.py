"""Unit tests for app.cartographer.parse.build_project_graph.

Hermetic: builds a small fixture repo under pytest's `tmp_path` and parses
it directly - no network, no git clone, no database. Cloning
(app.cartographer.ingest.clone_repo) is intentionally not exercised here
since it requires network access; only the local-directory path through
parse.build_project_graph is tested.
"""

from pathlib import Path

from app.cartographer.model import Edge, Node, ProjectGraph
from app.cartographer.parse import build_project_graph


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_fixture_repo(tmp_path: Path) -> Path:
    """Builds:

        repo/
            requirements.txt
            app/
                __init__.py
                main.py        (imports app.util, requests; has __main__ guard)
                util.py        (defines a class + function)
            .venv/ignored.py   (must be skipped)
    """
    root = tmp_path / "repo"

    _write(root / "requirements.txt", "requests>=2.0\nlanggraph==1.2.3\n# a comment\n-e .\n")

    _write(root / "app" / "__init__.py", "")

    _write(
        root / "app" / "util.py",
        (
            "class Helper:\n"
            "    pass\n"
            "\n"
            "def helper_func():\n"
            "    return 1\n"
        ),
    )

    _write(
        root / "app" / "main.py",
        (
            "import requests\n"
            "from app import util\n"
            "\n"
            "def main():\n"
            "    return util.helper_func()\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        ),
    )

    # Should be skipped entirely by the walker.
    _write(root / ".venv" / "ignored.py", "import should_not_appear\n")

    return root


def test_build_project_graph_returns_pydantic_models(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    assert isinstance(graph, ProjectGraph)
    assert all(isinstance(n, Node) for n in graph.nodes)
    assert all(isinstance(e, Edge) for e in graph.edges)


def test_build_project_graph_root_and_repo_url(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root), repo_url="https://example.com/org/repo.git")

    assert graph.root_path == str(root.resolve())
    assert graph.repo_url == "https://example.com/org/repo.git"


def test_build_project_graph_skips_ignored_dirs(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    node_paths = {n.path for n in graph.nodes if n.path}
    assert not any(".venv" in p for p in node_paths)
    ext_ids = {n.id for n in graph.nodes if n.type == "external_dep"}
    assert "ext:should_not_appear" not in ext_ids


def test_build_project_graph_module_nodes(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    ids = {n.id: n for n in graph.nodes}
    assert "module:app/main.py" in ids
    assert "module:app/util.py" in ids
    assert "module:app/__init__.py" in ids
    assert ids["module:app/main.py"].type == "module"
    assert ids["module:app/main.py"].language == "python"


def test_build_project_graph_contains_edges_hierarchy(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    repo_id = f"repo:{root.name}"
    contains = [(e.source, e.target) for e in graph.edges if e.type == "contains"]

    assert (repo_id, "package:app") in contains
    assert ("package:app", "module:app/main.py") in contains
    assert (repo_id, "file:requirements.txt") in contains


def test_build_project_graph_internal_import_edge(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    imports = [(e.source, e.target) for e in graph.edges if e.type == "imports"]
    # main.py does `from app import util` -> should resolve to the internal
    # app/util.py module node, not an external_dep.
    assert ("module:app/main.py", "module:app/util.py") in imports


def test_build_project_graph_external_import_edge(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    imports = [(e.source, e.target) for e in graph.edges if e.type == "imports"]
    assert ("module:app/main.py", "ext:requests") in imports

    ext_nodes = {n.id: n for n in graph.nodes if n.type == "external_dep"}
    assert "ext:requests" in ext_nodes


def test_build_project_graph_class_and_function_nodes(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    ids = {n.id for n in graph.nodes}
    assert "class:app/util.py:Helper" in ids
    assert "function:app/util.py:helper_func" in ids

    contains = [(e.source, e.target) for e in graph.edges if e.type == "contains"]
    assert ("module:app/util.py", "class:app/util.py:Helper") in contains
    assert ("module:app/util.py", "function:app/util.py:helper_func") in contains


def test_build_project_graph_manifests_and_depends_on(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    assert "requirements.txt" in graph.manifests
    assert set(graph.manifests["requirements.txt"]) == {"requests", "langgraph"}

    repo_id = f"repo:{root.name}"
    depends_on = [(e.source, e.target) for e in graph.edges if e.type == "depends_on"]
    assert (repo_id, "ext:requests") in depends_on
    assert (repo_id, "ext:langgraph") in depends_on


def test_build_project_graph_entrypoints(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    assert "module:app/main.py" in graph.entrypoints


def test_build_project_graph_stats(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root))

    assert graph.stats["nodes_by_type"]["module"] >= 3
    assert graph.stats["nodes_by_type"]["external_dep"] >= 1
    assert graph.stats["files"] >= 4
    assert "python" in graph.languages


def test_build_project_graph_raises_for_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    try:
        build_project_graph(str(missing))
        raised = False
    except NotADirectoryError:
        raised = True
    assert raised
