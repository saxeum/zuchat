"""Static UI: one HTML page and its JS/CSS, no build step."""

import html
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter(tags=["pages"])


@router.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


_DENIED = """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>not allowed</title>
    <link rel="stylesheet" href="/static/style.css" /></head>
  <body>
    <h1>Account not allowed</h1>
    <p>{who} is not on the allowlist for this server.</p>
    <p><a href="/login">Sign in with a different account</a></p>
  </body>
</html>
"""


def denied(email: str | None) -> HTMLResponse:
    """Return the page shown when a signed-in Google account is not allowlisted."""
    who = html.escape(email) if email else "That account"
    return HTMLResponse(_DENIED.format(who=who), status_code=403)
