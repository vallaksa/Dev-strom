"""User persistence for the auth layer: upsert on sign-in, fetch by id."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.services.db import get_session
from app.services.models import User


class EmailTakenError(Exception):
    """The email is already registered under a different provider.

    v1 does not auto-link accounts — identity is (auth_provider,
    provider_user_id). The user must sign in with the original provider.
    """

    def __init__(self, existing_provider: str):
        self.existing_provider = existing_provider
        super().__init__(f"email already registered via {existing_provider}")


def upsert_user(profile: dict) -> dict:
    """Insert or update a user from a normalized OAuth profile (see
    providers.exchange_code). Returns the user as a plain dict.
    """
    provider = profile["provider"]
    provider_user_id = profile["provider_user_id"]
    email = profile["email"]

    with get_session() as session:
        user = session.execute(
            select(User).where(
                User.auth_provider == provider,
                User.provider_user_id == provider_user_id,
            )
        ).scalar_one_or_none()

        if user is None:
            clash = session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            if clash is not None:
                raise EmailTakenError(clash.auth_provider)
            user = User(
                auth_provider=provider,
                provider_user_id=provider_user_id,
                email=email,
                name=profile.get("name"),
                avatar_url=profile.get("avatar_url"),
            )
            session.add(user)
        else:
            user.email = email
            user.name = profile.get("name")
            user.avatar_url = profile.get("avatar_url")

        session.flush()
        return _to_dict(user)


def get_user(user_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        user = session.get(User, user_id)
        return _to_dict(user) if user is not None else None


def _to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "auth_provider": user.auth_provider,
    }
