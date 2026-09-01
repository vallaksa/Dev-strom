"""JWT session token round-trip + provider profile normalization."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth import providers, session


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(session.settings, "session_secret", "unit-test-secret-that-is-at-least-32-bytes-long", raising=False)


def test_issue_then_read_round_trips():
    uid = uuid.uuid4()
    token = session.issue_token(uid)
    assert session.read_token(token) == uid


def test_expired_token_raises_session_error(monkeypatch):
    uid = uuid.uuid4()
    past = datetime.now(UTC) - timedelta(days=1)
    token = jwt.encode(
        {"sub": str(uid), "exp": int(past.timestamp())},
        "unit-test-secret-that-is-at-least-32-bytes-long",
        algorithm="HS256",
    )
    with pytest.raises(session.SessionError):
        session.read_token(token)


def test_token_signed_with_other_secret_raises():
    token = jwt.encode({"sub": str(uuid.uuid4())}, "someone-elses-secret", algorithm="HS256")
    with pytest.raises(session.SessionError):
        session.read_token(token)


def test_garbage_token_raises():
    with pytest.raises(session.SessionError):
        session.read_token("not-a-jwt")


# ── provider normalization ────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, *, token, get_map):
        self._token = token
        self._get_map = get_map

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, **kw):
        return _FakeResponse({"access_token": self._token})

    def get(self, url, **kw):
        return _FakeResponse(self._get_map[url])


def test_google_profile_normalized(monkeypatch):
    monkeypatch.setattr(providers.settings, "google_client_id", "x", raising=False)
    monkeypatch.setattr(providers.settings, "google_client_secret", "y", raising=False)
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **_: _FakeClient(
            token="tok",
            get_map={
                "https://openidconnect.googleapis.com/v1/userinfo": {
                    "sub": "1078",
                    "email": "Jo@example.com",
                    "email_verified": True,
                    "name": "Jo Dev",
                    "picture": "http://img/jo.png",
                }
            },
        ),
    )
    p = providers.exchange_code("google", "code123")
    assert p == {
        "provider": "google",
        "provider_user_id": "1078",
        "email": "jo@example.com",
        "name": "Jo Dev",
        "avatar_url": "http://img/jo.png",
    }


def test_github_falls_back_to_verified_primary_email(monkeypatch):
    monkeypatch.setattr(providers.settings, "github_client_id", "x", raising=False)
    monkeypatch.setattr(providers.settings, "github_client_secret", "y", raising=False)
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **_: _FakeClient(
            token="tok",
            get_map={
                "https://api.github.com/user": {"id": 42, "login": "jo", "name": None, "email": None,
                                                "avatar_url": "http://img/gh.png"},
                "https://api.github.com/user/emails": [
                    {"email": "old@x.com", "primary": False, "verified": True},
                    {"email": "jo@x.com", "primary": True, "verified": True},
                ],
            },
        ),
    )
    p = providers.exchange_code("github", "code123")
    assert p["provider_user_id"] == "42"
    assert p["email"] == "jo@x.com"
    assert p["name"] == "jo"  # falls back to login when name is null


def test_github_no_verified_email_raises(monkeypatch):
    monkeypatch.setattr(providers.settings, "github_client_id", "x", raising=False)
    monkeypatch.setattr(providers.settings, "github_client_secret", "y", raising=False)
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **_: _FakeClient(
            token="tok",
            get_map={
                "https://api.github.com/user": {"id": 7, "login": "x", "email": None},
                "https://api.github.com/user/emails": [
                    {"email": "u@x.com", "primary": True, "verified": False},
                ],
            },
        ),
    )
    with pytest.raises(providers.OAuthExchangeError):
        providers.exchange_code("github", "code123")
