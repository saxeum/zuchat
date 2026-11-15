"""Minimal client for the DeepSeek API."""

import http.client
import json
from collections.abc import Iterable, Iterator  # noqa: TC003 - used at runtime

API_HOST = "api.deepseek.com"


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


def _payload(message: str, model: str, *, stream: bool) -> str:
    return json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        },
    )


def _headers(api_key: str, **extra: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra,
    }


def chat(api_key: str, message: str, model: str = "deepseek-chat") -> str:
    """Send a single user message and return the assistant's reply."""
    conn = http.client.HTTPSConnection(API_HOST)
    try:
        conn.request(
            "POST",
            "/chat/completions",
            body=_payload(message, model, stream=False),
            headers=_headers(api_key),
        )
        resp = conn.getresponse()
        data = json.loads(resp.read())
    finally:
        conn.close()

    if resp.status != http.HTTPStatus.OK:
        msg = f"DeepSeek API error {resp.status}: {data}"
        raise RuntimeError(msg)

    return data["choices"][0]["message"]["content"]


def _deltas(lines: Iterable[bytes]) -> Iterator[str]:
    """Yield the content from the provider's `data:` frames until `[DONE]`.

    Blank lines, comments (`: keep-alive`) and the opening frame, which carries
    only a role, are skipped; frames without content yield nothing.
    """
    for raw in lines:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            return
        delta = json.loads(data)["choices"][0]["delta"].get("content")
        if delta:
            yield delta


def stream(
    api_key: str,
    message: str,
    model: str = "deepseek-chat",
) -> Iterator[str]:
    """Yield the reply as it arrives, one content delta at a time.

    DeepSeek speaks the OpenAI wire format: `data: {...}` per delta and a
    final `data: [DONE]`. Nothing is yielded until the first delta, so an
    error status surfaces before any text does.
    """
    conn = http.client.HTTPSConnection(API_HOST)
    try:
        conn.request(
            "POST",
            "/chat/completions",
            body=_payload(message, model, stream=True),
            headers=_headers(api_key, Accept="text/event-stream"),
        )
        resp = conn.getresponse()
        if resp.status != http.HTTPStatus.OK:
            msg = f"DeepSeek API error {resp.status}: {resp.read()!r}"
            raise RuntimeError(msg)

        yield from _deltas(resp)
    finally:
        conn.close()
