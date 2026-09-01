"""Authentication: Google + GitHub OAuth → JWT session cookie.

Public surface:
  - routes.router          — the /auth/* endpoints, mounted in app.api
  - deps.require_user      — FastAPI dependency returning the current User
  - deps.current_user_id   — same, as a bare UUID (for the persistence layer)

When settings.auth_enabled is False every request resolves to the seeded
anonymous user and no login gate is enforced.
"""
