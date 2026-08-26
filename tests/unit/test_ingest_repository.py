"""Unit tests for the deterministic repository ingestion in
app.cartographer.ingest.ingest_repository / repository_from_graph.

Hermetic: builds a small fixture repo under pytest's `tmp_path` and ingests
the local directory directly — no network, no git clone. A real `git init`
is used only in the commit-sha test (skipped if git is unavailable); the rest
run against a plain source dir where commit_sha is expected to be None.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.cartographer.ingest import (
    _extract_dependencies,
    _primary_language,
    ingest_repository,
    repository_from_graph,
)
from app.cartographer.parse import build_project_graph
from app.models.domain import Dependency, Repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "requirements.txt", "requests>=2.0\nlanggraph==1.2.3\n")
    _write(root / "package.json", '{"dependencies": {"react": "^18.0.0"}}')
    _write(root / "app" / "__init__.py", "")
    _write(root / "app" / "util.py", "class Helper:\n    pass\n\ndef helper_func():\n    return 1\n")
    _write(
        root / "app" / "main.py",
        'import requests\nfrom app import util\n\n'
        'def main():\n    return util.helper_func()\n\n'
        'if __name__ == "__main__":\n    main()\n',
    )
    return root


def test_ingest_repository_returns_repository_with_metadata(tmp_path):
    root = make_fixture_repo(tmp_path)
    repo = ingest_repository(str(root))

    assert isinstance(repo, Repository)
    assert repo.root_path == str(root.resolve())
    # local dir source -> no provenance URL, and (not a git tree) no commit
    assert repo.url is None
    assert repo.commit_sha is None
    assert repo.language == "python"        # only python code files present
    assert "python" in repo.languages
    assert repo.file_count >= 4
    assert repo.loc > 0
    assert "module:app/main.py" in repo.entrypoints


def test_ingest_repository_extracts_dependencies_by_ecosystem(tmp_path):
    root = make_fixture_repo(tmp_path)
    repo = ingest_repository(str(root))

    by_name = {d.name: d for d in repo.dependencies}
    assert {"requests", "langgraph", "react"} <= set(by_name)
    assert by_name["requests"].ecosystem == "pypi"
    assert by_name["requests"].source == "requirements.txt"
    assert by_name["react"].ecosystem == "npm"
    assert by_name["react"].source == "package.json"


def test_ingest_repository_id_is_deterministic(tmp_path):
    root = make_fixture_repo(tmp_path)
    a = ingest_repository(str(root))
    b = ingest_repository(str(root))
    # Same source + (no) commit -> stable id across ingests.
    assert a.id == b.id


def test_ingest_repository_records_provenance_url(tmp_path):
    root = make_fixture_repo(tmp_path)
    repo = ingest_repository(str(root), repo_url="https://example.com/org/repo.git")
    assert repo.url == "https://example.com/org/repo.git"


def test_repository_from_graph_is_pure(tmp_path):
    root = make_fixture_repo(tmp_path)
    graph = build_project_graph(str(root), repo_url="https://example.com/x.git")
    repo = repository_from_graph(graph, commit_sha="abc123")

    assert repo.commit_sha == "abc123"
    assert repo.url == "https://example.com/x.git"
    assert repo.language == "python"
    assert any(d.name == "requests" for d in repo.dependencies)


def test_extract_dependencies_tags_unknown_manifest():
    deps = _extract_dependencies({"weird.lock": ["foo", "bar"]})
    assert {d.ecosystem for d in deps} == {"unknown"}
    assert all(isinstance(d, Dependency) for d in deps)


def test_primary_language_picks_dominant_and_breaks_ties_alphabetically():
    assert _primary_language({"python": 10, "go": 3}) == "python"
    assert _primary_language({}) is None
    # tie -> alphabetical (deterministic)
    assert _primary_language({"go": 2, "python": 2}) == "go"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_ingest_repository_reads_commit_sha_from_git_tree(tmp_path):
    root = make_fixture_repo(tmp_path)
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True,
                   env={**subprocess.os.environ, **env})

    repo = ingest_repository(str(root))
    assert repo.commit_sha is not None
    assert len(repo.commit_sha) == 40  # full sha1
