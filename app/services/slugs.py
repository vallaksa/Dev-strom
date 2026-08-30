"""Human-readable public run IDs.

UUID remains the database primary key. API and UI `run_id` is a slug
derived from the repo URL (owner-repo) or idea intent, with -2, -3, …
on collision within a table.
"""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.services.db import get_session

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
MAX_SLUG_LEN = 48


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def slugify(value: str | None) -> str:
    text = _NON_ALNUM.sub("-", (value or "").strip().lower()).strip("-")
    text = text[:MAX_SLUG_LEN].strip("-")
    return text or "run"


def slug_from_repo(repo_url: str | None = None, path: str | None = None) -> str:
    if repo_url and repo_url.strip():
        return _slug_from_repo_url(repo_url.strip())
    if path and path.strip():
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        return slugify(parts[-1] if parts else path)
    return "run"


def unique_slug(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def allocate_slug(session, model, base: str) -> str:
    """Pick the first free slug for `model.slug`, querying the open session."""
    slug = base
    n = 2
    while session.execute(select(model.id).where(model.slug == slug)).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def insert_with_unique_slug(model, base: str, factory) -> str:
    """Insert a row with a unique slug, retrying on a concurrent unique violation.

    `factory(session, slug)` must return the mapped instance (not yet added).
    """
    last: BaseException | None = None
    for _ in range(8):
        try:
            with get_session() as session:
                slug = allocate_slug(session, model, base)
                row = factory(session, slug)
                session.add(row)
                session.flush()
                return public_id(row)
        except IntegrityError as exc:
            last = exc
            if "slug" not in str(exc).lower():
                raise
    assert last is not None
    raise last


def get_by_public_id(session, model, public_id: str):
    """Load a row by UUID primary key or by slug. Returns None if missing."""
    uid = parse_uuid(public_id)
    if uid is not None:
        row = session.get(model, uid)
        if row is not None:
            return row
    return session.execute(select(model).where(model.slug == public_id)).scalar_one_or_none()


def public_id(row) -> str:
    return row.slug or str(row.id)


def _slug_from_repo_url(repo_url: str) -> str:
    if repo_url.startswith("git@"):
        path = repo_url.split(":", 1)[-1]
        parts = [p for p in path.removesuffix(".git").split("/") if p]
    else:
        parsed = urlparse(repo_url)
        parts = [p for p in parsed.path.removesuffix(".git").split("/") if p]
    if len(parts) >= 2:
        return slugify(f"{parts[-2]}-{parts[-1]}")
    if parts:
        return slugify(parts[-1])
    return slugify(repo_url)
