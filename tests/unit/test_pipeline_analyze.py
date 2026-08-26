"""Unit test for app.cartographer.pipeline.analyze_repository orchestration.

Hermetic: runs against a local fixture directory (no clone) and monkeypatches
the LLM findings pass so the deterministic ingest + wiring is what's exercised,
not a real model call. Confirms the single-parse pipeline hands a real,
graph-derived Repository to analyze_findings and returns its Analysis.
"""

from pathlib import Path

import app.cartographer.pipeline as pipeline
from app.models.domain import Analysis, Repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "requirements.txt", "requests>=2.0\n")
    _write(root / "app" / "__init__.py", "")
    _write(root / "app" / "main.py",
           'import requests\n\ndef main():\n    return 1\n\n'
           'if __name__ == "__main__":\n    main()\n')
    return root


def test_analyze_repository_wires_ingest_into_findings(tmp_path, monkeypatch):
    root = _fixture_repo(tmp_path)
    captured = {}

    def fake_analyze_findings(graph, repository):
        captured["graph"] = graph
        captured["repository"] = repository
        return Analysis(id="a1", repository=repository, summary="ok", status="complete")

    monkeypatch.setattr(pipeline, "analyze_findings", fake_analyze_findings)

    analysis = pipeline.analyze_repository(str(root))

    assert isinstance(analysis, Analysis)
    assert analysis.status == "complete"
    # the Repository handed to findings was derived from the real parsed graph
    repo = captured["repository"]
    assert isinstance(repo, Repository)
    assert repo.language == "python"
    assert any(d.name == "requests" for d in repo.dependencies)
    assert "module:app/main.py" in repo.entrypoints
    # analysis carries that same repository through
    assert analysis.repository.id == repo.id
