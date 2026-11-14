"""Sign-in, callback, and sign-out."""

import os
from urllib.parse import urlsplit

from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from zuchat.auth import app_base_url, is_allowed, oauth
from zuchat.pages import denied

router = APIRouter(tags=["auth"])


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Send the browser to Google's account chooser."""
    base = app_base_url().rstrip("/")
    # Canonicalise the HOST only. Behind the ALB the request arrives as http
    # (TLS terminated upstream), so comparing schemes redirects https -> https
    # forever. The scheme is decided by APP_BASE_URL, not by the request.
    want = urlsplit(base)
    have = request.url
    if (have.hostname, have.port) != (want.hostname, want.port):
        return RedirectResponse(f"{base}/login", status_code=302)
    if not os.environ.get("SESSION_SECRET"):
        raise HTTPException(status_code=500, detail="SESSION_SECRET is not set")
    return await oauth.google.authorize_redirect(
        request, f"{base}/auth", prompt="select_account",
    )


@router.get("/auth", name="auth")
async def auth(request: Request) -> Response:
    """OAuth callback: verify, allowlist, then remember the user in the session."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except MismatchingStateError:
        # Stale or missing session: start over rather than showing a 500.
        request.session.clear()
        return RedirectResponse("/login")

    user = token.get("userinfo") or {}
    email = user.get("email")
    if not is_allowed(email):
        request.session.clear()
        return denied()

    request.session["user"] = {"email": email, "name": user.get("name", "")}
    return RedirectResponse("/")


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/")
