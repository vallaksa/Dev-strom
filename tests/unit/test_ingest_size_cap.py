"""Regression: the ingest size-cap must skip the same heavy dirs the parser
ignores (.venv, .git, node_modules, ...), so a local checkout with a virtualenv
or committed dependencies is not falsely rejected."""

import pytest

from app.cartographer import ingest
from app.cartographer.ingest import IngestError, _check_size_caps


def _write(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_size_cap_skips_ignored_dirs(tmp_path, monkeypatch):
    # A tiny source tree...
    _write(tmp_path / "app" / "main.py", 100)
    # ...next to a heavy .venv that must NOT count toward the cap.
    _write(tmp_path / ".venv" / "big.bin", 5000)
    _write(tmp_path / ".git" / "objects" / "pack.bin", 5000)

    monkeypatch.setattr(ingest, "MAX_REPO_BYTES", 1000)  # 1 KB cap
    # Should pass: only the 100-byte source file counts.
    _check_size_caps(tmp_path)


def test_size_cap_still_trips_on_real_content(tmp_path, monkeypatch):
    _write(tmp_path / "app" / "big.py", 5000)
    monkeypatch.setattr(ingest, "MAX_REPO_BYTES", 1000)
    with pytest.raises(IngestError):
        _check_size_caps(tmp_path)
