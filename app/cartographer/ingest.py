"""Repo ingestion: turn a git URL or local path into a local directory ready
for parsing.

Uses the system `git` binary via subprocess (no GitPython dependency -
stdlib + the `git` CLI already required to run this project is enough for a
shallow clone). Shallow clones are written under a dedicated tempfile prefix
so `cleanup_clone` can safely remove them without risking a caller-supplied
local path.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── guards ───────────────────────────────────────────────────────────────────
# Cheap caps to avoid accidentally cloning/parsing something huge. These are
# intentionally generous - they exist to catch mistakes (wrong URL, monorepo
# with vendored binaries), not to be a tight resource budget.
MAX_REPO_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_REPO_FILES = 50_000

# Schemes git itself accepts for `git clone`, plus the scp-like
# "git@host:path" shorthand (which urlparse does not treat as having a
# scheme, so it is detected separately below).
_ALLOWED_URL_SCHEMES = {"http", "https", "git", "ssh"}

_TMP_PREFIX = "cartographer-clone-"


class IngestError(ValueError):
    """Raised for invalid sources, oversized repos, or clone failures."""


def _looks_like_scp_git_url(value: str) -> bool:
    """Detect the scp-like `user@host:path` git URL shorthand.

    e.g. "git@github.com:org/repo.git" - urlparse would parse this as a
    scheme-less path, so we special-case it rather than misclassify it as a
    local path.
    """
    if "://" in value:
        return False
    at, _, rest = value.partition("@")
    return bool(at) and ":" in rest and " " not in value


def _validate_repo_url(repo_url: str) -> None:
    if _looks_like_scp_git_url(repo_url):
        return
    parsed = urlparse(repo_url)
    if parsed.scheme not in _ALLOWED_URL_SCHEMES:
        raise IngestError(
            f"Unsupported or missing URL scheme in {repo_url!r}; "
            f"expected one of {sorted(_ALLOWED_URL_SCHEMES)} or an scp-like git URL."
        )
    if not parsed.netloc:
        raise IngestError(f"Malformed repo URL (no host): {repo_url!r}")


# Directories excluded from the size-cap walk — mirror parse.py's ignore set so a
# local checkout's .git / .venv / node_modules don't falsely trip the cap on repos
# we can otherwise parse fine (those dirs are skipped during parsing anyway).
_SIZE_IGNORE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".gradle",
})


def _check_size_caps(root: Path) -> None:
    total_bytes = 0
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored dirs in-place so os.walk doesn't descend into them.
        dirnames[:] = [
            d for d in dirnames
            if d not in _SIZE_IGNORE_DIRS and not d.endswith(".egg-info")
        ]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink() or not p.is_file():
                continue
            total_files += 1
            total_bytes += p.stat().st_size
            if total_files > MAX_REPO_FILES:
                raise IngestError(
                    f"Repo at {root} exceeds the {MAX_REPO_FILES}-file cap; refusing to ingest."
                )
            if total_bytes > MAX_REPO_BYTES:
                raise IngestError(
                    f"Repo at {root} exceeds the {MAX_REPO_BYTES // (1024 * 1024)}MB cap; "
                    "refusing to ingest."
                )


def clone_repo(repo_url: str, dest: str | None = None, depth: int = 1) -> str:
    """Shallow-clone `repo_url` and return the local path it was cloned to.

    Args:
        repo_url: http(s)/git/ssh URL (or scp-like `git@host:path`).
        dest: target directory. Defaults to a fresh tempdir under the
            `cartographer-clone-` prefix so `cleanup_clone` can identify and
            remove it later.
        depth: history depth for the shallow clone (1 = tip commit only).

    Raises:
        IngestError: on an invalid URL, a failed clone, or a repo that
            exceeds the size/file-count caps (the partial clone is removed
            before raising).
    """
    _validate_repo_url(repo_url)

    target = Path(dest) if dest else Path(tempfile.mkdtemp(prefix=_TMP_PREFIX))
    target.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth", str(max(1, depth)), "--single-branch", repo_url, str(target)]
    logger.info("Cloning %s (depth=%d) -> %s", repo_url, depth, target)
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise IngestError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        cleanup_clone(str(target))
        raise IngestError(f"Timed out cloning {repo_url!r}") from exc
    except subprocess.CalledProcessError as exc:
        cleanup_clone(str(target))
        raise IngestError(f"git clone failed for {repo_url!r}: {exc.stderr.strip()}") from exc

    try:
        _check_size_caps(target)
    except IngestError:
        cleanup_clone(str(target))
        raise

    return str(target)


def cleanup_clone(path: str) -> None:
    """Remove a directory previously created by `clone_repo`.

    Refuses to touch anything outside the tempdir prefix used by
    `clone_repo`, so it is always safe to call on a path of unknown origin
    (e.g. in a `finally` block) without risking deletion of a caller-supplied
    local repo.
    """
    p = Path(path)
    if p.name.startswith(_TMP_PREFIX) or f"/{_TMP_PREFIX}" in str(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        logger.debug("cleanup_clone: skipping %s (not a cartographer temp clone)", path)


def resolve_source(url_or_path: str, depth: int = 1) -> str:
    """Resolve a user-supplied repo URL or local path to a local root path
    ready for parsing.

    An existing local directory is returned as-is (absolute path); anything
    else is validated as a git URL and shallow-cloned via `clone_repo`.

    Raises:
        IngestError: invalid URL, clone failure, or oversized repo.
    """
    candidate = Path(url_or_path).expanduser()
    if candidate.is_dir():
        logger.info("Using existing local directory as source: %s", candidate)
        resolved = str(candidate.resolve())
        _check_size_caps(Path(resolved))
        return resolved

    return clone_repo(url_or_path, depth=depth)
