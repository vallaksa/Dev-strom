"""Structural parser: walk a local repo root and build a normalized
ProjectGraph (app.cartographer.model.ProjectGraph).

Python is parsed with stdlib `ast` for imports and top-level class/function
extraction. Every other language gets file-tree nodes only (no deep parse) -
that is an explicit, documented limitation, not an oversight; see the
module docstring in model.py for why the contract stays language-agnostic.

Dependency manifests (requirements.txt, pyproject.toml, package.json,
go.mod, pom.xml) are parsed opportunistically - whichever of these exist at
the repo root are added to `manifests` and turned into `external_dep` nodes.
"""

import ast
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.cartographer.model import Edge, Node, ProjectGraph

logger = logging.getLogger(__name__)

# ── walk config ──────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "egg-info",
}

# Extension -> language label. Anything not listed here still gets a `file`
# node; `language` is just left None.
EXTENSION_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".sh": "shell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
}

# Only these count toward `ProjectGraph.languages` / per-language stats -
# markup/config extensions are still given file nodes+language, but they'd
# make the "languages" summary noisy.
CODE_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "go",
    "java",
    "ruby",
    "rust",
    "c",
    "cpp",
    "csharp",
    "php",
    "shell",
    "sql",
}

MANIFEST_FILENAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "pom.xml",
}

MAX_MEMBERS_PER_MODULE = 200  # cap class/function nodes extracted per .py file
ENTRYPOINT_BASENAMES = {"main.py", "manage.py", "app.py", "wsgi.py", "asgi.py"}


# ── small helpers ────────────────────────────────────────────────────────────


def _posix(rel: Path) -> str:
    return rel.as_posix()


def _ext_dep_id(name: str) -> str:
    return f"ext:{name.strip().lower()}"


class _GraphBuilder:
    """Mutable accumulator used while walking; `.build()` returns the
    immutable ProjectGraph."""

    def __init__(self, root_path: Path, repo_url: str | None):
        self.root_path = root_path
        self.repo_url = repo_url
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.entrypoints: list[str] = []
        self.language_counts: dict[str, int] = {}
        self.loc = 0
        self.file_count = 0
        # dotted python module name -> node id, used to resolve `import a.b.c`
        self.py_module_index: dict[str, str] = {}

    def add_node(self, node: Node) -> Node:
        """Insert a node if new; if it already exists (e.g. an external_dep
        discovered both via imports and a manifest), keep the first and
        just note the extra source in meta."""
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return node
        sources = set(existing.meta.get("sources", [existing.meta.get("source")] if existing.meta.get("source") else []))
        new_source = node.meta.get("source")
        if new_source:
            sources.add(new_source)
            existing.meta["sources"] = sorted(s for s in sources if s)
            existing.meta.pop("source", None)
        return existing

    def add_edge(self, source: str, target: str, type: str, meta: dict | None = None) -> None:
        self.edges.append(Edge(source=source, target=target, type=type, meta=meta or {}))

    def build(self) -> ProjectGraph:
        nodes_by_type: dict[str, int] = {}
        for n in self.nodes.values():
            nodes_by_type[n.type] = nodes_by_type.get(n.type, 0) + 1
        edges_by_type: dict[str, int] = {}
        for e in self.edges:
            edges_by_type[e.type] = edges_by_type.get(e.type, 0) + 1

        return ProjectGraph(
            repo_url=self.repo_url,
            root_path=str(self.root_path),
            languages=sorted(self.language_counts),
            nodes=list(self.nodes.values()),
            edges=self.edges,
            entrypoints=self.entrypoints,
            manifests={},  # filled in by build_project_graph after manifest parsing
            stats={
                "files": self.file_count,
                "nodes_by_type": nodes_by_type,
                "edges_by_type": edges_by_type,
                "languages": self.language_counts,
                "loc": self.loc,
            },
        )


# ── tree walk ────────────────────────────────────────────────────────────────


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.endswith(".egg-info")


def _walk_tree(g: _GraphBuilder, repo_id: str) -> list[tuple[Path, str]]:
    """Walk the directory tree, emitting package/file nodes and `contains`
    edges. Returns a list of (absolute_path, node_id) for every .py file
    found, for the second-pass import parsing.

    Uses os.walk-style manual recursion (via Path.iterdir) so directory
    pruning is trivial and deterministic (sorted).
    """
    py_files: list[tuple[Path, str]] = []

    def node_id_for_dir(rel: Path) -> str:
        return repo_id if rel == Path(".") else f"package:{_posix(rel)}"

    def recurse(abs_dir: Path, rel_dir: Path) -> None:
        parent_id = node_id_for_dir(rel_dir)
        try:
            entries = sorted(abs_dir.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            logger.warning("Skipping unreadable directory %s: %s", abs_dir, exc)
            return

        for entry in entries:
            if entry.is_symlink():
                continue
            rel_entry = rel_dir / entry.name if rel_dir != Path(".") else Path(entry.name)

            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                pkg_id = f"package:{_posix(rel_entry)}"
                g.add_node(
                    Node(
                        id=pkg_id,
                        type="package",
                        label=entry.name,
                        path=_posix(rel_entry),
                    )
                )
                g.add_edge(parent_id, pkg_id, "contains")
                recurse(entry, rel_entry)
            elif entry.is_file():
                g.file_count += 1
                ext = entry.suffix.lower()
                language = EXTENSION_LANGUAGES.get(ext)
                if language in CODE_LANGUAGES:
                    g.language_counts[language] = g.language_counts.get(language, 0) + 1
                try:
                    g.loc += sum(1 for _ in entry.open("r", encoding="utf-8", errors="ignore"))
                except OSError:
                    pass

                if ext == ".py":
                    file_id = f"module:{_posix(rel_entry)}"
                    node_type = "module"
                else:
                    file_id = f"file:{_posix(rel_entry)}"
                    node_type = "file"

                g.add_node(
                    Node(
                        id=file_id,
                        type=node_type,
                        label=entry.name,
                        path=_posix(rel_entry),
                        language=language,
                    )
                )
                g.add_edge(parent_id, file_id, "contains")

                if ext == ".py":
                    py_files.append((entry, file_id))
                    dotted = _dotted_module_name(rel_entry)
                    if dotted:
                        g.py_module_index[dotted] = file_id

    recurse(g.root_path, Path("."))
    return py_files


def _dotted_module_name(rel_path: Path) -> str | None:
    """app/services/db.py -> "app.services.db"; app/__init__.py -> "app"."""
    parts = list(rel_path.with_suffix("").parts)
    if not parts:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


# ── python import + member extraction ───────────────────────────────────────


def _resolve_dotted(g: _GraphBuilder, dotted: str) -> str | None:
    """Find the longest prefix of `dotted` that matches a known internal
    python module, e.g. "app.services.db.something" resolves via
    "app.services.db" if that module exists."""
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in g.py_module_index:
            return g.py_module_index[candidate]
    return None


def _parse_python_file(
    g: _GraphBuilder,
    abs_path: Path,
    module_id: str,
    rel_path: Path,
    *,
    include_members: bool = False,
) -> None:
    try:
        source = abs_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(rel_path))
    except (SyntaxError, ValueError) as exc:
        logger.warning("Failed to parse %s: %s", rel_path, exc)
        return

    # current module's package, for resolving relative imports (from . import x)
    pkg_parts = list(rel_path.parent.parts)

    member_count = 0
    has_dunder_main = False
    has_main_func = False
    has_app_assignment = False

    for stmt in tree.body:
        if member_count >= MAX_MEMBERS_PER_MODULE:
            break

        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                _emit_import_edge(g, module_id, alias.name)

        elif isinstance(stmt, ast.ImportFrom):
            if stmt.level and stmt.level > 0:
                # relative import: resolve against the current package
                base_parts = pkg_parts[: len(pkg_parts) - (stmt.level - 1)] if stmt.level > 1 else pkg_parts
                base = ".".join(base_parts)
                target = f"{base}.{stmt.module}" if stmt.module else base
            else:
                target = stmt.module or ""
            if target:
                # `from app import util` imports a *submodule* (resolves to
                # app.util as a module), while `from app.util import Helper`
                # imports a *symbol* from within app.util. ast gives both the
                # same shape, so try each imported name as `target.name`
                # first and only fall back to `target` itself if none of
                # them resolve to a known internal module.
                resolved_submodule = False
                for alias in stmt.names:
                    sub_target = f"{target}.{alias.name}"
                    if sub_target in g.py_module_index:
                        _emit_import_edge(g, module_id, sub_target)
                        resolved_submodule = True
                if not resolved_submodule:
                    _emit_import_edge(g, module_id, target)

        elif isinstance(stmt, ast.ClassDef):
            if not include_members:
                continue
            class_id = f"class:{_posix(rel_path)}:{stmt.name}"
            g.add_node(Node(id=class_id, type="class", label=stmt.name, path=_posix(rel_path)))
            g.add_edge(module_id, class_id, "contains")
            member_count += 1

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_members:
                if stmt.name == "main":
                    has_main_func = True
                continue
            func_id = f"function:{_posix(rel_path)}:{stmt.name}"
            g.add_node(Node(id=func_id, type="function", label=stmt.name, path=_posix(rel_path)))
            g.add_edge(module_id, func_id, "contains")
            member_count += 1
            if stmt.name == "main":
                has_main_func = True

        # ── entrypoint heuristics (cheap, top-level-statement scan) ────────
        if isinstance(stmt, ast.If) and _is_dunder_main_guard(stmt):
            has_dunder_main = True
        if isinstance(stmt, ast.Assign) and _assigns_fastapi_or_similar(stmt):
            has_app_assignment = True

    if (
        has_dunder_main
        or has_app_assignment
        or has_main_func
        or abs_path.name in ENTRYPOINT_BASENAMES
        or "scripts" in pkg_parts
        or "bin" in pkg_parts
    ):
        g.entrypoints.append(module_id)
        g.nodes[module_id].meta["entrypoint"] = True


def _is_dunder_main_guard(stmt: ast.If) -> bool:
    test = stmt.test
    # if __name__ == "__main__":
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__":
        return True
    return False


def _assigns_fastapi_or_similar(stmt: ast.Assign) -> bool:
    call = stmt.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return name in {"FastAPI", "Flask", "APIRouter"}


def _emit_import_edge(g: _GraphBuilder, module_id: str, dotted: str) -> None:
    internal_target = _resolve_dotted(g, dotted)
    if internal_target and internal_target != module_id:
        g.add_edge(module_id, internal_target, "imports")
        return
    if internal_target == module_id:
        return  # self-import (rare), skip

    top_level = dotted.split(".")[0]
    ext_id = _ext_dep_id(top_level)
    g.add_node(
        Node(
            id=ext_id,
            type="external_dep",
            label=top_level,
            meta={"source": "import"},
        )
    )
    g.add_edge(module_id, ext_id, "imports")


# ── manifest parsing ─────────────────────────────────────────────────────────


def _strip_requirement_name(line: str) -> str | None:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-r", "-e", "--")):
        return None
    name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
    return name or None


def _parse_requirements_txt(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        name = _strip_requirement_name(line)
        if name:
            names.append(name)
    return names


def _parse_pyproject_toml(text: str) -> list[str]:
    try:
        import tomllib
    except ImportError:  # pragma: no cover - py<3.11 fallback, not expected here
        return []
    try:
        data = tomllib.loads(text)
    except Exception as exc:
        logger.warning("Failed to parse pyproject.toml: %s", exc)
        return []

    names: list[str] = []
    for dep in data.get("project", {}).get("dependencies", []):
        name = _strip_requirement_name(dep)
        if name:
            names.append(name)
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name in poetry_deps:
        if name.lower() != "python":
            names.append(name)
    return names


def _parse_package_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse package.json: %s", exc)
        return []
    names: list[str] = []
    for key in ("dependencies", "devDependencies"):
        names.extend(data.get(key, {}).keys())
    return names


def _parse_go_mod(text: str) -> list[str]:
    names: list[str] = []
    in_block = False
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if in_block:
            parts = line.split()
            if parts:
                names.append(parts[0])
        elif line.startswith("require "):
            parts = line[len("require ") :].split()
            if parts:
                names.append(parts[0])
    return names


def _parse_pom_xml(text: str) -> list[str]:
    names: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("Failed to parse pom.xml: %s", exc)
        return []
    # Namespace-agnostic: match any tag ending in "}artifactId" or "artifactId".
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "dependency":
            for child in elem:
                if child.tag.rsplit("}", 1)[-1] == "artifactId" and child.text:
                    names.append(child.text.strip())
    return names


_MANIFEST_PARSERS = {
    "requirements.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "package.json": _parse_package_json,
    "go.mod": _parse_go_mod,
    "pom.xml": _parse_pom_xml,
}


def _parse_manifests(g: _GraphBuilder, repo_id: str) -> dict:
    manifests: dict[str, list[str]] = {}
    for filename, parser in _MANIFEST_PARSERS.items():
        manifest_path = g.root_path / filename
        if not manifest_path.is_file():
            continue
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning("Could not read %s: %s", manifest_path, exc)
            continue
        deps = parser(text)
        manifests[filename] = deps
        for dep_name in deps:
            ext_id = _ext_dep_id(dep_name)
            g.add_node(
                Node(
                    id=ext_id,
                    type="external_dep",
                    label=dep_name,
                    meta={"source": filename},
                )
            )
            g.add_edge(repo_id, ext_id, "depends_on", meta={"manifest": filename})
    return manifests


# ── entry point ──────────────────────────────────────────────────────────────


def build_project_graph(
    root_path: str,
    repo_url: str | None = None,
    *,
    include_members: bool = False,
) -> ProjectGraph:
    """Walk `root_path` and build a normalized ProjectGraph.

    By default skips class/function nodes (`include_members=False`) — the
    pipeline rolls the graph up to system level via `aggregate.to_system_graph`.
    """
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"root_path is not a directory: {root_path}")

    repo_id = f"repo:{root.name or 'repo'}"
    g = _GraphBuilder(root_path=root, repo_url=repo_url)
    g.add_node(Node(id=repo_id, type="repo", label=root.name or str(root), path="."))

    py_files = _walk_tree(g, repo_id)

    for abs_path, module_id in py_files:
        rel_path = abs_path.relative_to(root)
        _parse_python_file(g, abs_path, module_id, rel_path, include_members=include_members)

    manifests = _parse_manifests(g, repo_id)

    graph = g.build()
    graph.manifests.update(manifests)
    logger.info(
        "Built ProjectGraph for %s: %d nodes, %d edges, %d entrypoints",
        root,
        len(graph.nodes),
        len(graph.edges),
        len(graph.entrypoints),
    )
    return graph
