"""Application wiring."""

import os
from collections.abc import AsyncIterator  # noqa: TC003 - evaluated at runtime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from zuchat import api_routes, auth_routes, ops_routes, pages
from zuchat.auth import app_base_url, session_secret
from zuchat.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast: a task without the key should die, not serve 500s."""
    get_settings()
    if not os.environ.get("SESSION_SECRET"):
        msg = "SESSION_SECRET is not set - start with `make up` (it loads the config)"
        raise RuntimeError(msg)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Zuchat", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        same_site="lax",
        https_only=app_base_url().startswith("https"),
    )
    app.mount("/static", StaticFiles(directory=pages.STATIC_DIR), name="static")
    app.include_router(pages.router)
    app.include_router(auth_routes.router)
    app.include_router(ops_routes.router)
    app.include_router(api_routes.router)
    return app


api = create_app()
