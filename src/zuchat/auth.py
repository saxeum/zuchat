"""Google sign-in (OpenID Connect) via authlib.

Configuration comes from the environment:

    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET   OAuth client (console.cloud.google.com)
    SESSION_SECRET                          signs the session cookie
    ALLOWED_EMAILS                          optional comma-separated allowlist
    APP_BASE_URL                            public origin, for https-only cookies

Locally the Makefile loads ~/.config/zuchat/google-oauth.env if it exists.
"""

import os
import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status

GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=GOOGLE_DISCOVERY,
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    client_kwargs={"scope": "openid email profile"},
)


def session_secret() -> str:
    """Return a stable secret in prod, an ephemeral one in dev."""
    return os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)


def app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:8000")


def allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def is_allowed(email: str | None) -> bool:
    """Empty allowlist means 'any Google account'; set it to lock the app down."""
    allow = allowed_emails()
    if not email:
        return False
    return not allow or email.lower() in allow


def current_user(request: Request) -> dict[str, str]:
    """Dependency: the signed-in user, or 401."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login required: open /login",
        )
    return user
