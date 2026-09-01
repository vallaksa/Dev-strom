"""JWT session token + cookie helpers.

The session is a stateless HS256 JWT carrying only the user id and an
expiry. It rides in an HttpOnly, SameSite=Lax cookie (Secure when the app
is served over https). Logout just clears the cookie — there is no
server-side session store, so a token stays valid until it expires.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from app.config import settings

COOKIE_NAME = "ds_session"
_ALGO = "HS256"


class SessionError(Exception):
    """Raised when a session token is missing, malformed, or expired."""


def _secret() -> str:
    if not settings.session_secret:
        raise RuntimeError(
            "SESSION_SECRET is not set — required when AUTH_ENABLED=true."
        )
    return settings.session_secret


def issue_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.session_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def read_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise SessionError(str(exc)) from exc


def set_session_cookie(response: Response, user_id: uuid.UUID) -> None:
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user_id),
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
