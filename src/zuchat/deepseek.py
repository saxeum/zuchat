"""Minimal client for the DeepSeek API."""

import http.client
import json
from collections.abc import Iterable, Iterator  # noqa: TC003 - used at runtime
from dataclasses import dataclass, field

API_HOST = "api.deepseek.com"


@dataclass(frozen=True)
class Usage:
    """What the provider says a request cost, in tokens."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        """Tokens the request is billed for."""
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Reply:
    """One complete answer, with the cost the provider reported."""

    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class Chunk:
    """One streamed fragment: a piece of text, or the usage at the end."""

    text: str = ""
    usage: Usage | None = None


def _payload(
    message: str,
    model: str,
    *,
    stream: bool,
    max_tokens: int | None,
) -> str:
    body: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": stream,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if stream:
        # Without this the provider sends no usage frame, and a streamed reply
        # could not be charged what it actually cost.
        body["stream_options"] = {"include_usage": True}
    return json.dumps(body)


def _headers(api_key: str, **extra: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra,
    }


def _first_choice(frame: dict[str, object]) -> dict[str, object] | None:
    choices = frame.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    return first if isinstance(first, dict) else None


def _content(frame: dict[str, object], key: str) -> str:
    """Return the text at choices[0][key][content], or "" when absent."""
    choice = _first_choice(frame)
    if choice is None:
        return ""
    body = choice.get(key)
    if not isinstance(body, dict):
        return ""
    text = body.get("content")
    return text if isinstance(text, str) else ""


def _usage(frame: dict[str, object]) -> Usage:
    """Return the `usage` object, tolerating frames that carry none."""
    raw = frame.get("usage")
    if not isinstance(raw, dict):
        return Usage()
    prompt = raw.get("prompt_tokens")
    completion = raw.get("completion_tokens")
    return Usage(
        prompt_tokens=prompt if isinstance(prompt, int) else 0,
        completion_tokens=completion if isinstance(completion, int) else 0,
    )


def _chunks(lines: Iterable[bytes]) -> Iterator[Chunk]:
    """Yield the text in the provider's `data:` frames, then any usage.

    Blank lines, comments (`: keep-alive`) and frames carrying only a role are
    skipped.
    """
    for raw in lines:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            return
        frame = json.loads(data)
        if not isinstance(frame, dict):
            continue
        text = _content(frame, "delta")
        if text:
            yield Chunk(text=text)
        if frame.get("usage"):
            yield Chunk(usage=_usage(frame))


def models(api_key: str) -> list[dict[str, object]]:
    """Return the models available to the given API key."""
    conn = http.client.HTTPSConnection(API_HOST)
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        conn.request("GET", "/models", headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read())
    finally:
        conn.close()

    if resp.status != http.HTTPStatus.OK:
        msg = f"DeepSeek API error {resp.status}: {data}"
        raise RuntimeError(msg)

    return data["data"]


def chat(
    api_key: str,
    message: str,
    model: str = "deepseek-chat",
    *,
    max_tokens: int | None = None,
) -> Reply:
    """Send a single user message and return the reply with its token cost."""
    conn = http.client.HTTPSConnection(API_HOST)
    try:
        conn.request(
            "POST",
            "/chat/completions",
            body=_payload(message, model, stream=False, max_tokens=max_tokens),
            headers=_headers(api_key),
        )
        resp = conn.getresponse()
        data = json.loads(resp.read())
    finally:
        conn.close()

    if resp.status != http.HTTPStatus.OK:
        msg = f"DeepSeek API error {resp.status}: {data}"
        raise RuntimeError(msg)

    return Reply(text=_content(data, "message"), usage=_usage(data))


def stream(
    api_key: str,
    message: str,
    model: str = "deepseek-chat",
    *,
    max_tokens: int | None = None,
) -> Iterator[Chunk]:
    """Yield the reply as it arrives, ending with a usage chunk.

    DeepSeek speaks the OpenAI wire format: `data: {...}` per delta, a usage
    frame when asked for one, then `data: [DONE]`. Nothing is yielded until the
    first delta, so an error status surfaces before any text does.
    """
    conn = http.client.HTTPSConnection(API_HOST)
    try:
        conn.request(
            "POST",
            "/chat/completions",
            body=_payload(message, model, stream=True, max_tokens=max_tokens),
            headers=_headers(api_key, Accept="text/event-stream"),
        )
        resp = conn.getresponse()
        if resp.status != http.HTTPStatus.OK:
            msg = f"DeepSeek API error {resp.status}: {resp.read()!r}"
            raise RuntimeError(msg)

        yield from _chunks(resp)
    finally:
        conn.close()
