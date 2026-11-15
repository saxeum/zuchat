"""Authenticated JSON API. Everything under /api requires a session."""

import json
import logging
import math
from collections.abc import Iterator  # noqa: TC003 - used at runtime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from zuchat import deepseek, ratelimit
from zuchat.auth import current_user
from zuchat.deps import deepseek_api_key

logger = logging.getLogger("zuchat")

# One dependency at the router level: every /api route is authenticated, and a
# new route cannot forget it.
router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(current_user)])


class ChatRequest(BaseModel):
    """Capped so a public endpoint cannot be used to send megabyte prompts."""

    message: str = Field(min_length=1, max_length=4000)


def chat_quota(user: Annotated[dict[str, str], Depends(current_user)]) -> None:
    """Charge one chat request to the caller, then to the shared budget.

    Per-user first: one noisy account must not be able to empty the budget
    everyone shares. The counters live in this process, so they reset when the
    task restarts.
    """
    limits = ratelimit.get_limits()
    wait = limits.per_user.retry_after(user["email"])
    if not wait:
        wait = limits.everyone.retry_after(ratelimit.EVERYONE)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many requests; try again shortly",
            headers={"Retry-After": str(math.ceil(wait))},
        )


@router.get("/me")
def me(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
    """Who the session belongs to."""
    return user


@router.get("/models")
def models(
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> list[dict[str, object]]:
    return deepseek.models(api_key)


@router.post("/chat", dependencies=[Depends(chat_quota)])
def chat(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> dict[str, str]:
    return {"reply": deepseek.chat(api_key, request.message)}


@router.post("/chat/stream", dependencies=[Depends(chat_quota)])
def chat_stream(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> StreamingResponse:
    """Stream the same answer as server-sent events, one partial per frame."""
    return StreamingResponse(
        _events(api_key, request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _events(api_key: str, message: str) -> Iterator[str]:
    """Yield `data:` frames of text, then `data: [DONE]`.

    The status line is already sent by the time the provider answers, so a
    failure has to be reported in-band as an `error` frame.
    """
    try:
        for delta in deepseek.stream(api_key, message):
            yield f"data: {json.dumps({'text': delta})}\n\n"
    except (OSError, RuntimeError) as exc:
        logger.warning("stream failed: %s", exc)
        yield 'event: error\ndata: {"detail": "provider request failed"}\n\n'
    yield "data: [DONE]\n\n"
