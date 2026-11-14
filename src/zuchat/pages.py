"""Static UI: HTML pages plus their JS/CSS, no build step."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter(tags=["pages"])


@router.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")



def denied() -> FileResponse:
    """Return the static page for a Google account that is not allowlisted."""
    return FileResponse(STATIC_DIR / "denied.html", status_code=403)
