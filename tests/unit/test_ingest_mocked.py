"""Mocked unit tests for app.cartographer.ingest clone/resolve/cleanup paths.

Hermetic: never runs a real `git clone`. subprocess.run is monkeypatched so
URL validation, temp-dir lifecycle, size-cap failure cleanup, and local-path
resolution are exercised without network or the git CLI.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.cartographer import ingest
from app.cartographer.ingest import (
    IngestError,
    cleanup_clone,
    clone_repo,
    resolve_source,
)


def test_clone_repo_rejects_unsupported_scheme():
    with pytest.raises(IngestError, match="Unsupported or missing URL scheme"):
        clone_repo("ftp://example.com/repo.git")


def test_clone_repo_rejects_url_without_host():
    with pytest.raises(IngestError, match="no host"):
        clone_repo("https:///missing-host")


def test_clone_repo_accepts_scp_like_git_url(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    monkeypatch.setattr(ingest, "_check_size_caps", lambda root: None)

    dest = tmp_path / "clone"
    path = clone_repo("git@github.com:org/repo.git", dest=str(dest))

    assert path == str(dest)
    assert calls["cmd"][:3] == ["git", "clone", "--depth"]
    assert calls["cmd"][-2] == "git@github.com:org/repo.git"


def test_clone_repo_mocks_successful_https_clone(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        assert cmd[0] == "git" and cmd[1] == "clone"
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    monkeypatch.setattr(ingest, "_check_size_caps", lambda root: None)

    dest = tmp_path / "https-clone"
    assert clone_repo("https://github.com/org/repo.git", dest=str(dest), depth=2) == str(dest)


def test_clone_repo_wraps_called_process_error_and_cleans_up(monkeypatch, tmp_path):
    cleaned = []

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(128, cmd, stderr="fatal: repository not found")

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    monkeypatch.setattr(ingest, "cleanup_clone", lambda p: cleaned.append(p))

    dest = tmp_path / "fail-clone"
    with pytest.raises(IngestError, match="git clone failed"):
        clone_repo("https://github.com/org/missing.git", dest=str(dest))

    assert cleaned == [str(dest)]


def test_clone_repo_wraps_timeout_and_cleans_up(monkeypatch, tmp_path):
    cleaned = []

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)
    monkeypatch.setattr(ingest, "cleanup_clone", lambda p: cleaned.append(p))

    dest = tmp_path / "timeout-clone"
    with pytest.raises(IngestError, match="Timed out"):
        clone_repo("https://github.com/org/slow.git", dest=str(dest))

    assert cleaned == [str(dest)]


def test_clone_repo_missing_git_binary(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(ingest.subprocess, "run", fake_run)

    with pytest.raises(IngestError, match="git executable not found"):
        clone_repo("https://github.com/org/repo.git", dest=str(tmp_path / "nogit"))


def test_clone_repo_size_cap_failure_cleans_partial_clone(monkeypatch, tmp_path):
    cleaned = []

    monkeypatch.setattr(
        ingest.subprocess,
        "run",
        lambda *a, **k: MagicMock(returncode=0, stdout="", stderr=""),
    )
    def boom(_root):
        raise IngestError("too big")

    monkeypatch.setattr(ingest, "_check_size_caps", boom)
    monkeypatch.setattr(ingest, "cleanup_clone", lambda p: cleaned.append(p))

    dest = tmp_path / "huge"
    with pytest.raises(IngestError, match="too big"):
        clone_repo("https://github.com/org/huge.git", dest=str(dest))

    assert cleaned == [str(dest)]


def test_cleanup_clone_removes_temp_prefix_dirs(tmp_path):
    clone = tmp_path / f"{ingest._TMP_PREFIX}abc"
    clone.mkdir()
    (clone / "file.txt").write_text("x", encoding="utf-8")
    cleanup_clone(str(clone))
    assert not clone.exists()


def test_cleanup_clone_skips_non_temp_paths(tmp_path):
    safe = tmp_path / "my-local-repo"
    safe.mkdir()
    (safe / "keep.txt").write_text("keep", encoding="utf-8")
    cleanup_clone(str(safe))
    assert safe.exists()
    assert (safe / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_resolve_source_returns_local_dir_without_cloning(tmp_path, monkeypatch):
    root = tmp_path / "local"
    root.mkdir()
    (root / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.setattr(ingest, "_check_size_caps", lambda p: None)
    called = {"clone": False}
    monkeypatch.setattr(
        ingest,
        "clone_repo",
        lambda *a, **k: called.__setitem__("clone", True) or "/tmp/nope",
    )

    resolved = resolve_source(str(root))
    assert Path(resolved) == root.resolve()
    assert called["clone"] is False


def test_resolve_source_clones_when_not_a_directory(monkeypatch):
    monkeypatch.setattr(ingest, "clone_repo", lambda url, depth=1: f"/tmp/cloned-{depth}")
    assert resolve_source("https://github.com/org/repo.git", depth=3) == "/tmp/cloned-3"
