"""/auth/* endpoints: OAuth login start, callback, session identity, logout."""

from __future__ import annotations

import logging
import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from app.auth import providers, service, session
from app.auth.deps import require_user
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_COOKIE = "ds_oauth_state"
_STATE_MAX_AGE = 600  # 10 minutes to complete the round trip


def _serializer() -> URLSafeTimedSerializer:
    if not settings.session_secret:
        raise HTTPException(503, "Auth is enabled but SESSION_SECRET is not set")
    return URLSafeTimedSerializer(settings.session_secret, salt="oauth-state")


def _safe_next(raw: str | None) -> str:
    """Only allow same-app relative paths as the post-login redirect target."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/ideas"


@router.get("/providers")
def list_providers() -> dict:
    """Which providers are configured — the login page renders a button per entry."""
    return {"providers": providers.configured_providers()}


@router.get("/me")
def me(request: Request) -> dict:
    return require_user(request)


@router.post("/logout")
def logout(response: Response) -> Response:
    session.clear_session_cookie(response)
    response.status_code = 204
    return response


class MockLogin(BaseModel):
    email: str
    name: str | None = None


@router.post("/mock")
def mock_login(body: MockLogin, response: Response) -> dict:
    """Dev-only passwordless sign-in (MOCK_AUTH=true). Enter an email and
    you become that user — a new one the first time, the same one after."""
    if not providers.is_configured("mock"):
        raise HTTPException(404, "Mock sign-in is not enabled")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email")
    user = service.upsert_user({
        "provider": "mock",
        "provider_user_id": email,
        "email": email,
        "name": body.name or email.split("@")[0].replace(".", " ").title(),
        "avatar_url": None,
    })
    session.set_session_cookie(response, uuid.UUID(user["id"]))
    return user


@router.get("/{provider}/login")
def login(provider: str, request: Request, next: str | None = None) -> RedirectResponse:
    if not providers.is_supported(provider):
        raise HTTPException(404, f"Unknown provider {provider!r}")
    if not providers.is_configured(provider):
        raise HTTPException(503, f"{provider} sign-in is not configured on this server")

    nonce = secrets.token_urlsafe(16)
    state = _serializer().dumps({"n": nonce, "p": provider, "next": _safe_next(next)})

    redirect = RedirectResponse(providers.build_authorize_url(provider, state))
    redirect.set_cookie(
        _STATE_COOKIE,
        state,
        max_age=_STATE_MAX_AGE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/{provider}/callback")
def callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    web = settings.web_base_url.rstrip("/")

    if error:
        return RedirectResponse(f"{web}/login?error={error}")
    if not code or not state or state != request.cookies.get(_STATE_COOKIE):
        return RedirectResponse(f"{web}/login?error=bad_state")

    try:
        data = _serializer().loads(state, max_age=_STATE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return RedirectResponse(f"{web}/login?error=bad_state")
    if data.get("p") != provider:
        return RedirectResponse(f"{web}/login?error=bad_state")

    try:
        profile = providers.exchange_code(provider, code)
        user = service.upsert_user(profile)
    except service.EmailTakenError as exc:
        return RedirectResponse(f"{web}/login?error=email_taken&provider={exc.existing_provider}")
    except providers.OAuthExchangeError as exc:
        logger.warning("OAuth exchange failed for %s: %s", provider, exc)
        return RedirectResponse(f"{web}/login?error=oauth_failed")
    except Exception:
        logger.exception("Unexpected error in %s callback", provider)
        return RedirectResponse(f"{web}/login?error=server_error")

    redirect = RedirectResponse(f"{web}{_safe_next(data.get('next'))}")
    session.set_session_cookie(redirect, uuid.UUID(user["id"]))
    redirect.delete_cookie(_STATE_COOKIE, path="/")
    return redirect
