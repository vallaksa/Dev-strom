"""OAuth provider config + the code→profile exchange for Google and GitHub.

Kept deliberately dependency-light: a plain httpx round-trip per provider
rather than a full OAuth framework, so the flow is easy to read and to
monkeypatch in tests. `exchange_code` returns a normalized profile:

    {"provider": "google", "provider_user_id": "...", "email": "...",
     "name": "...", "avatar_url": "..."}
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

Provider = str  # "google" | "github"


@dataclass(frozen=True)
class _ProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    scope: str
    client_id: str | None
    client_secret: str | None


def _configs() -> dict[str, _ProviderConfig]:
    return {
        "google": _ProviderConfig(
            name="google",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        ),
        "github": _ProviderConfig(
            name="github",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
        ),
    }


def is_supported(provider: str) -> bool:
    return provider in ("google", "github")


def is_configured(provider: str) -> bool:
    cfg = _configs().get(provider)
    return bool(cfg and cfg.client_id and cfg.client_secret)


def configured_providers() -> list[str]:
    return [p for p in ("google", "github") if is_configured(p)]


def redirect_uri(provider: str) -> str:
    return f"{settings.api_base_url.rstrip('/')}/auth/{provider}/callback"


def build_authorize_url(provider: str, state: str) -> str:
    cfg = _configs()[provider]
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri(provider),
        "response_type": "code",
        "scope": cfg.scope,
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{cfg.authorize_url}?{urlencode(params)}"


class OAuthExchangeError(Exception):
    """The provider rejected the code, or gave us no usable email."""


def exchange_code(provider: str, code: str) -> dict:
    cfg = _configs()[provider]
    with httpx.Client(timeout=15) as http:
        token_res = http.post(
            cfg.token_url,
            data={
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "code": code,
                "redirect_uri": redirect_uri(provider),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_res.status_code != 200:
            raise OAuthExchangeError(f"{provider} token exchange failed ({token_res.status_code})")
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise OAuthExchangeError(f"{provider} returned no access token")

        if provider == "google":
            return _google_profile(http, access_token)
        return _github_profile(http, access_token)


def _google_profile(http: httpx.Client, access_token: str) -> dict:
    res = http.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    res.raise_for_status()
    info = res.json()
    email = info.get("email")
    if not email or not info.get("email_verified", True):
        raise OAuthExchangeError("Google account has no verified email")
    return {
        "provider": "google",
        "provider_user_id": str(info["sub"]),
        "email": email.lower(),
        "name": info.get("name"),
        "avatar_url": info.get("picture"),
    }


def _github_profile(http: httpx.Client, access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    user = http.get("https://api.github.com/user", headers=headers)
    user.raise_for_status()
    u = user.json()

    email = u.get("email")
    if not email:
        emails = http.get("https://api.github.com/user/emails", headers=headers)
        emails.raise_for_status()
        primary = next(
            (e for e in emails.json() if e.get("primary") and e.get("verified")),
            None,
        ) or next((e for e in emails.json() if e.get("verified")), None)
        email = primary["email"] if primary else None
    if not email:
        raise OAuthExchangeError(
            "No verified email on the GitHub account — add one or make it public"
        )
    return {
        "provider": "github",
        "provider_user_id": str(u["id"]),
        "email": email.lower(),
        "name": u.get("name") or u.get("login"),
        "avatar_url": u.get("avatar_url"),
    }
