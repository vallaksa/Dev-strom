"""Auth endpoints + the login gate on data routes."""

import uuid

import pytest

from app import api as api_module
from app.auth import deps as deps_module
from app.auth import routes as routes_module
from app.auth import session as session_module


@pytest.fixture()
def auth_on(monkeypatch):
    """Enable the login gate with a known session secret."""
    for mod in (deps_module.settings, session_module.settings, routes_module.settings):
        monkeypatch.setattr(mod, "auth_enabled", True, raising=False)
        monkeypatch.setattr(mod, "session_secret", "integration-secret-at-least-32-bytes-padded", raising=False)
    return "integration-secret-at-least-32-bytes-padded"


def _cookie_for(user_id: str) -> dict:
    return {session_module.COOKIE_NAME: session_module.issue_token(uuid.UUID(user_id))}


# ── auth disabled (default) ───────────────────────────────────────────────────

def test_auth_disabled_me_returns_anonymous(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["auth_provider"] == "system"


def test_auth_disabled_history_is_open(client, monkeypatch):
    monkeypatch.setattr(api_module, "load_history", lambda **kw: [])
    assert client.get("/history").status_code == 200


# ── auth enabled ──────────────────────────────────────────────────────────────

def test_gated_route_401_without_cookie(client, auth_on):
    assert client.get("/history").status_code == 401


def test_gated_route_401_with_garbage_cookie(client, auth_on):
    resp = client.get("/history", cookies={session_module.COOKIE_NAME: "nope"})
    assert resp.status_code == 401


def test_gated_route_passes_with_valid_session(client, auth_on, monkeypatch):
    uid = str(uuid.uuid4())
    monkeypatch.setattr(deps_module.service, "get_user", lambda _id: {"id": uid, "email": "a@b.c",
                                                                     "name": "A", "avatar_url": None,
                                                                     "auth_provider": "google"})
    seen = {}
    monkeypatch.setattr(api_module, "load_history",
                        lambda **kw: seen.update(kw) or [])
    resp = client.get("/history", cookies=_cookie_for(uid))
    assert resp.status_code == 200
    assert seen["user_id"] == uuid.UUID(uid)


def test_logout_clears_cookie(client, auth_on):
    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    assert "ds_session=" in resp.headers.get("set-cookie", "")


def test_login_unknown_provider_404(client, auth_on):
    assert client.get("/auth/wechat/login").status_code == 404


def test_login_unconfigured_provider_503(client, auth_on):
    # auth_on doesn't set client id/secret → provider is not "configured"
    assert client.get("/auth/google/login", follow_redirects=False).status_code == 503


def test_callback_bad_state_redirects_to_login(client, auth_on):
    resp = client.get(
        "/auth/google/callback",
        params={"code": "x", "state": "tampered"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "/login?error=bad_state" in resp.headers["location"]


def test_providers_lists_configured(client, monkeypatch):
    monkeypatch.setattr(routes_module.providers, "configured_providers", lambda: ["github"])
    assert client.get("/auth/providers").json() == {"providers": ["github"]}
