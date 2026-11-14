"""Minimal client for the DeepSeek API."""

import http.client
import json

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


def chat(api_key: str, message: str, model: str = "deepseek-chat") -> str:
    """Send a single user message and return the assistant's reply."""
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": message}]},
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    conn = http.client.HTTPSConnection(API_HOST)
    try:
        conn.request("POST", "/chat/completions", body=payload, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read())
    finally:
        conn.close()

    if resp.status != http.HTTPStatus.OK:
        msg = f"DeepSeek API error {resp.status}: {data}"
        raise RuntimeError(msg)

    return data["choices"][0]["message"]["content"]
