import html
import os
from collections.abc import AsyncIterator  # noqa: TC003 - evaluated at runtime
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from zuchat import deepseek
from zuchat.auth import app_base_url, current_user, is_allowed, oauth, session_secret
from zuchat.config import Settings, get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast: a task without the key should die, not serve 500s."""
    get_settings()
    yield


api = FastAPI(title="Zuchat", version="0.1.0", lifespan=lifespan)
api.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    same_site="lax",
    https_only=app_base_url().startswith("https"),
)


@api.get("/login", tags=["auth"])
async def login(request: Request) -> RedirectResponse:
    """Send the browser to Google's consent screen.

    The redirect URI comes from APP_BASE_URL, not from the request Host header:
    Google compares it character-for-character, and 127.0.0.1 vs localhost is
    the most common way that comparison fails.
    """
    base = app_base_url().rstrip("/")
    # Canonicalise the origin first. The OAuth state lives in the session
    # cookie, which is scoped to the host the browser used; the callback goes to
    # redirect_uri's host. If those differ (127.0.0.1 vs localhost), the state is
    # never sent back and authlib raises MismatchingStateError.
    if str(request.base_url).rstrip("/") != base:
        return RedirectResponse(f"{base}/login", status_code=302)
    if not os.environ.get("SESSION_SECRET"):
        raise HTTPException(status_code=500, detail="SESSION_SECRET is not set")
    # Always show the account chooser. Without it Google silently reuses the
    # last account (prompt=none), so a rejected user is bounced back into the
    # same 403 loop instead of being offered another account.
    return await oauth.google.authorize_redirect(
        request, f"{base}/auth", prompt="select_account",
    )


@api.get("/auth", name="auth", tags=["auth"])
async def auth(request: Request) -> RedirectResponse:
    """OAuth callback: verify, allowlist, then store the user in the session."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except MismatchingStateError:
        # Stale/absent session (wrong host, secret rotated, expired cookie):
        # start over instead of showing a 500.
        request.session.clear()
        return RedirectResponse("/login")
    user = token.get("userinfo") or {}
    email = user.get("email")
    if not is_allowed(email):
        request.session.clear()
        return HTMLResponse(
            f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>not allowed</title></head><body style="font-family:system-ui;margin:3rem">
<h1>Account not allowed</h1>
<p>{html.escape(email or "That account")} is not on the allowlist.</p>
<p><a href="/login">Sign in with a different account</a></p>
</body></html>""",
            status_code=403,
        )
    request.session["user"] = {"email": email, "name": user.get("name", "")}
    return RedirectResponse("/")


@api.get("/logout", tags=["auth"])
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/")


def deepseek_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """FastAPI dependency: the DeepSeek key from the environment."""
    return settings.deepseek_api_key.get_secret_value()


class ChatRequest(BaseModel):
    message: str


PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>zuchat</title>
<style>body{{font-family:system-ui;margin:3rem;max-width:32rem}}</style></head>
<body>
  <h1>zuchat</h1>
  <p>{status}</p>
  <ul>
    <li><a href="/models">models</a></li>
    <li>{action}</li>
  </ul>
</body>
</html>
"""


@api.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    user = request.session.get("user")
    if user:
        status = f"Signed in as {html.escape(user.get('email', ''))}"
        action = '<a href="/logout">logout</a>'
    else:
        status = "Not signed in."
        action = '<a href="/login">login</a>'
    return PAGE.format(status=status, action=action)


@api.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness: the process is up. Touches no dependencies.

    Used by the ALB target group / ECS container health check.
    """
    return {"status": "ok"}


@api.get("/ready", tags=["ops"], responses={503: {"description": "not ready"}})
def ready() -> dict[str, str]:
    """Readiness: this task can serve traffic.

    Checks the one thing that would make requests fail: the API key. It does
    not call DeepSeek, so it stays cheap and cannot be rate limited.
    """
    try:
        key = get_settings().deepseek_api_key.get_secret_value()
    except ValidationError:
        key = ""
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="deepseek api key is not configured",
        )
    return {"status": "ready"}


@api.get("/models")
def get_models(
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> list[dict[str, object]]:
    return deepseek.models(api_key)


@api.post("/chat")
def chat(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
    _user: Annotated[dict[str, str], Depends(current_user)],
) -> dict[str, str]:
    reply = deepseek.chat(api_key, request.message)
    return {"reply": reply}


def main() -> None:
    uvicorn.run("zuchat.main:api", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
