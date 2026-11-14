"""Scratch: what does the openai library give us against DeepSeek? Not used by the app."""

import os
import time
from pathlib import Path

from openai import OpenAI

key = os.environ.get("DEEPSEEK_API_KEY") or (
    Path.home() / ".config" / "zuchat" / "deepseek.token"
).read_text().strip()

client = OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=30, max_retries=0)

try:
    print("models:", [m.id for m in client.models.list().data])
except Exception as exc:  # noqa: BLE001
    print("models: FAILED", type(exc).__name__, exc)

reply = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Reply with exactly: pong"}],
)
print("reply:", reply.choices[0].message.content)
print("usage:", reply.usage)

start = time.monotonic()
first = None
text = ""
for chunk in client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Count from 1 to 5."}],
    stream=True,
):
    delta = chunk.choices[0].delta.content or ""
    if delta and first is None:
        first = time.monotonic() - start
    text += delta
print(f"stream: first_token={first:.2f}s total={time.monotonic() - start:.2f}s text={text[:40]!r}")
