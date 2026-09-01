"""FastAPI dependencies for the current user.

`require_user` is attached to every data route. Behaviour:
  - AUTH_ENABLED=false  → always the seeded anonymous user (local dev).
  - AUTH_ENABLED=true   → decode the session cookie; 401 if missing/invalid.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, Request

from app.auth import service, session
from app.config import settings
from app.services.models import ANONYMOUS_USER_ID

_ANON = {
    "id": str(ANONYMOUS_USER_ID),
    "email": "anonymous@devstrom.local",
    "name": "Anonymous",
    "avatar_url": None,
    "auth_provider": "system",
}


def require_user(request: Request) -> dict:
    """Return the current user dict, or raise 401."""
    if not settings.auth_enabled:
        return _ANON

    token = request.cookies.get(session.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user_id = session.read_token(token)
    except session.SessionError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def current_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(require_user(request)["id"])
