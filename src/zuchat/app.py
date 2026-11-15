"""Application wiring."""

import os
from collections.abc import AsyncIterator  # noqa: TC003 - evaluated at runtime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from zuchat import api_routes, auth_routes, bodylimit, ops_routes, pages, ratelimit
from zuchat.auth import app_base_url, session_secret
from zuchat.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast: a task with broken config should die, not serve 500s."""
    get_settings()
    ratelimit.get_limits()
    if not os.environ.get("SESSION_SECRET"):
        msg = "SESSION_SECRET is not set - start with `make up` (it loads the config)"
        raise RuntimeError(msg)
    yield


def create_app() -> FastAPI:
    # Docs are useful in dev and container testing, and unnecessary attack
    # surface in production; ECS sets ENABLE_DOCS=false.
    docs = os.environ.get("ENABLE_DOCS", "true").lower() not in {"0", "false", "no"}
    app = FastAPI(
        title="Zuchat",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        same_site="lax",
        https_only=app_base_url().startswith("https"),
        # A signed cookie cannot be revoked (see #64), so its lifetime is the
        # exposure window. Short by default; existing cookies older than this
        # are rejected on their next request.
        max_age=int(os.environ.get("SESSION_MAX_AGE_SECONDS", "86400")),
    )
    # Ahead of session and auth handling: an anonymous caller must not be able
    # to make the task parse a large body (see bodylimit).
    app.add_middleware(
        bodylimit.BodyLimit,
        max_bytes=int(
            os.environ.get("MAX_BODY_BYTES", str(bodylimit.MAX_BODY_BYTES)),
        ),
    )
    app.mount("/static", StaticFiles(directory=pages.STATIC_DIR), name="static")
    app.include_router(pages.router)
    app.include_router(auth_routes.router)
    app.include_router(ops_routes.router)
    app.include_router(api_routes.router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # noqa: ANN001, ANN202
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # /auth carries an OAuth code in the query string: never leak it in a Referer.
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        if app_base_url().startswith("https"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    return app


api = create_app()
