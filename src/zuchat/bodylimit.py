"""Refuse oversized request bodies before anything parses them.

FastAPI parses a body before the auth dependency rejects an unauthenticated
request, and the 4,000-character cap on `ChatRequest.message` applies only
after parsing. So without this, an anonymous client can make the task decode
arbitrary amounts of JSON — measured at 50 MB in about twenty seconds.

The body is buffered up to a small ceiling and replayed to the app, which keeps
the streaming disconnect semantics intact: once the body is consumed, further
reads go to the real receive again.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send  # noqa: TC002 - used at runtime

MAX_BODY_BYTES = 64 * 1024


class BodyLimit:
    """Buffer a request body up to `max_bytes`; refuse anything larger."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        """Set the ceiling; 0 or less disables the check."""
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject early on Content-Length, then enforce while buffering."""
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _reject(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await _reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": bytes(body),
                    "more_body": False,
                }
            # The body is spent: a streaming response still needs the real
            # channel to notice a disconnect, so do not fake one.
            return await receive()

        await self.app(scope, replay, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
    """Answer 413 without reading the body at all."""
    response = JSONResponse({"detail": "request body too large"}, status_code=413)
    await response(scope, receive, send)
