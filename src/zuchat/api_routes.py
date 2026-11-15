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

User = dict[str, str]


class ChatRequest(BaseModel):
    """Capped so a public endpoint cannot be used to send megabyte prompts."""

    message: str = Field(min_length=1, max_length=4000)


def _too_many(wait: float, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(max(1, math.ceil(wait)))},
    )


def chat_quota(user: Annotated[User, Depends(current_user)]) -> None:
    """Charge the request rate, then check the token budgets.

    Request counts bound bursts; token budgets bound the bill, which is what
    the provider actually charges for. Per-user first in both cases: one noisy
    account must not empty the budget everyone shares.
    """
    limits = ratelimit.get_limits()

    wait = limits.per_user.hit(user["email"])
    if not wait:
        wait = limits.everyone.hit(ratelimit.EVERYONE)
    if wait:
        raise _too_many(wait, "too many requests; try again shortly")

    wait = limits.tokens_per_user.retry_after(user["email"])
    if not wait:
        wait = limits.tokens_everyone.retry_after(ratelimit.EVERYONE)
    if wait:
        raise _too_many(wait, "the token budget is used up; try again later")


def _acquire(email: str) -> None:
    """One reply at a time per user: parallel streams are the real fan-out."""
    if not ratelimit.get_limits().in_flight.acquire(email):
        raise _too_many(1.0, "a reply is already in progress; wait for it")


def _release(email: str) -> None:
    ratelimit.get_limits().in_flight.release(email)


@router.get("/me")
def me(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
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
    user: Annotated[User, Depends(current_user)],
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> dict[str, str]:
    limits = ratelimit.get_limits()
    _acquire(user["email"])
    try:
        reply = deepseek.chat(
            api_key,
            request.message,
            max_tokens=limits.max_output_tokens,
        )
    finally:
        _release(user["email"])
    ratelimit.record(user["email"], reply.usage.total)
    return {"reply": reply.text}


@router.post("/chat/stream", dependencies=[Depends(chat_quota)])
def chat_stream(
    request: ChatRequest,
    user: Annotated[User, Depends(current_user)],
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> StreamingResponse:
    """Stream the same answer as server-sent events, one partial per frame."""
    _acquire(user["email"])
    return StreamingResponse(
        _events(user["email"], api_key, request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _events(email: str, api_key: str, message: str) -> Iterator[str]:
    """Yield `data:` frames of text, then `data: [DONE]`.

    The status line is already sent by the time the provider answers, so a
    failure has to be reported in-band as an `error` frame. Whatever the stream
    cost is charged when it ends, including a stream the client abandoned.
    """
    limits = ratelimit.get_limits()
    reply = ""
    usage: deepseek.Usage | None = None
    failed = False
    try:
        chunks = deepseek.stream(
            api_key,
            message,
            max_tokens=limits.max_output_tokens,
        )
        for chunk in chunks:
            if chunk.text:
                reply += chunk.text
                yield f"data: {json.dumps({'text': chunk.text})}\n\n"
            if chunk.usage:
                usage = chunk.usage
    except (OSError, RuntimeError) as exc:
        logger.warning("stream failed: %s", exc)
        failed = True
    finally:
        # A reply that never produced text cost nothing worth charging.
        tokens = usage.total if usage else 0
        if not usage and reply:
            tokens = ratelimit.estimate_tokens(message) + ratelimit.estimate_tokens(
                reply,
            )
        ratelimit.record(email, tokens)
        _release(email)
    if failed:
        yield 'event: error\ndata: {"detail": "provider request failed"}\n\n'
    yield "data: [DONE]\n\n"
