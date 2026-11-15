"""Tests for the Zuchat HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from zuchat import deepseek, ratelimit
from zuchat.app import create_app
from zuchat.auth import current_user, is_allowed, oauth
from zuchat.config import get_settings
from zuchat.deps import deepseek_api_key
from zuchat.main import api

if TYPE_CHECKING:
    from collections.abc import Iterator

TEST_API_KEY = "test-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Hermetic client: fake key in the environment, dependency overridden."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    # Generous by default: only the tests that care about the quota should trip it.
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_MINUTE", "1000")
    get_settings.cache_clear()
    ratelimit.get_limits.cache_clear()
    api.dependency_overrides[deepseek_api_key] = lambda: TEST_API_KEY
    api.dependency_overrides[current_user] = lambda: {"email": "test@example.com"}
    yield TestClient(api)
    api.dependency_overrides.clear()
    get_settings.cache_clear()
    ratelimit.get_limits.cache_clear()


def test_index(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="composer"' in response.text
    assert "/static/app.js" in response.text


def test_index_references_assets_that_are_served(client: TestClient) -> None:
    page = client.get("/").text

    assert "/static/theme.css" in page
    assert "/static/app.css" in page
    assert "/static/style.css" not in page

    for asset in (
        "/static/theme.css",
        "/static/app.css",
        "/static/favicon.svg",
        "/static/fonts/geist-latin-wght-normal.woff2",
    ):
        served = client.get(asset)
        assert served.status_code == 200, asset
        assert served.content, asset


def test_me_requires_login() -> None:
    api.dependency_overrides.pop(current_user, None)
    assert TestClient(api).get("/api/me").status_code == 401


def test_me_returns_user(client: TestClient) -> None:
    assert client.get("/api/me").json() == {"email": "test@example.com"}


def test_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_EMAILS", "a@example.com, b@example.com")
    assert is_allowed("a@example.com")
    assert is_allowed("B@Example.com")
    assert not is_allowed("c@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", "")
    assert is_allowed("anyone@example.com")
    assert not is_allowed(None)


def test_login_redirects_to_canonical_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "http://canonical.example")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    other = TestClient(api, base_url="http://elsewhere.example")
    response = other.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://canonical.example/login"


def test_disallowed_account_gets_a_page_and_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_EMAILS", "allowed@example.com")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    async def fake_token(_request: object) -> dict[str, object]:
        return {"userinfo": {"email": "other@example.com", "name": "Other"}}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake_token)

    response = TestClient(api).get("/auth?state=x&code=y", follow_redirects=False)

    assert response.status_code == 403
    assert "not allowed" in response.text.lower()
    assert 'href="/login"' in response.text


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_key_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  sk-abc123\n")
    get_settings.cache_clear()
    assert get_settings().deepseek_api_key.get_secret_value() == "sk-abc123"


def test_ready(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_without_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()
    response = client.get("/ready")
    assert response.status_code == 503


def test_chat_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    get_settings.cache_clear()
    api.dependency_overrides.pop(current_user, None)
    try:
        response = TestClient(api).post("/api/chat", json={"message": "hi"})
        assert response.status_code == 401
    finally:
        api.dependency_overrides[current_user] = lambda: {"email": "test@example.com"}
        get_settings.cache_clear()


def test_models_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    get_settings.cache_clear()
    api.dependency_overrides.pop(current_user, None)
    try:
        assert TestClient(api).get("/api/models").status_code == 401
    finally:
        api.dependency_overrides[current_user] = lambda: {"email": "test@example.com"}
        get_settings.cache_clear()


def test_chat_rejects_oversized_message(client: TestClient) -> None:
    assert client.post("/api/chat", json={"message": "x" * 4001}).status_code == 422
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_models_uses_configured_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_models(api_key: str) -> list[dict[str, str]]:
        seen["api_key"] = api_key
        return [{"id": "deepseek-chat"}]

    monkeypatch.setattr(deepseek, "models", fake_models)

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.json() == [{"id": "deepseek-chat"}]
    assert seen["api_key"] == TEST_API_KEY


def test_chat_sends_message_to_api(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_chat(api_key: str, message: str) -> str:
        seen["api_key"] = api_key
        seen["message"] = message
        return "hello back"

    monkeypatch.setattr(deepseek, "chat", fake_chat)

    response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "hello back"}
    assert seen == {"api_key": TEST_API_KEY, "message": "hello"}


def test_stream_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    get_settings.cache_clear()
    api.dependency_overrides.pop(current_user, None)
    try:
        response = TestClient(api).post("/api/chat/stream", json={"message": "hi"})
        assert response.status_code == 401
    finally:
        api.dependency_overrides[current_user] = lambda: {"email": "test@example.com"}
        get_settings.cache_clear()


def test_stream_sends_deltas_then_done(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_stream(api_key: str, message: str) -> Iterator[str]:
        seen["api_key"] = api_key
        seen["message"] = message
        yield "hel"
        yield "lo"

    monkeypatch.setattr(deepseek, "stream", fake_stream)

    response = client.post("/api/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == (
        'data: {"text": "hel"}\n\ndata: {"text": "lo"}\n\ndata: [DONE]\n\n'
    )
    assert seen == {"api_key": TEST_API_KEY, "message": "hello"}


def test_stream_reports_a_provider_failure_in_band(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_stream(_api_key: str, _message: str) -> Iterator[str]:
        msg = "provider down"
        raise RuntimeError(msg)
        yield  # unreachable: a raise on first iteration is the case under test

    monkeypatch.setattr(deepseek, "stream", fake_stream)

    response = client.post("/api/chat/stream", json={"message": "hello"})

    # The status line is already on the wire, so the failure is an event.
    assert response.status_code == 200
    assert "event: error" in response.text
    assert response.text.endswith("data: [DONE]\n\n")


def test_stream_rejects_oversized_message(client: TestClient) -> None:
    assert (
        client.post(
            "/api/chat/stream",
            json={"message": "x" * 4001},
        ).status_code
        == 422
    )
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 422


def test_stream_parses_provider_frames() -> None:
    lines = [
        b": keep-alive\n",
        b"\n",
        b'data: {"choices": [{"delta": {"role": "assistant"}}]}\n',
        b'data: {"choices": [{"delta": {"content": "hel"}}]}\n',
        b'data: {"choices": [{"delta": {"content": "lo"}}]}\n',
        b"data: [DONE]\n",
        b'data: {"choices": [{"delta": {"content": "ignored"}}]}\n',
    ]

    # The parser is the part a live reply cannot cover in a unit test.
    assert list(deepseek._deltas(lines)) == ["hel", "lo"]  # noqa: SLF001


def _set_limits(
    monkeypatch: pytest.MonkeyPatch,
    per_user: int,
    everyone: int,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(per_user))
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_MINUTE", str(everyone))
    ratelimit.get_limits.cache_clear()


def _fake_chat(_api_key: str, _message: str) -> str:
    return "ok"


def _fake_stream(_api_key: str, _message: str) -> Iterator[str]:
    yield "ok"


def test_chat_is_rate_limited_per_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_limits(monkeypatch, per_user=1, everyone=0)
    monkeypatch.setattr(deepseek, "chat", _fake_chat)

    first = client.post("/api/chat", json={"message": "one"})
    second = client.post("/api/chat", json={"message": "two"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
    assert "too many requests" in second.json()["detail"]


def test_stream_shares_the_chat_budget(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_limits(monkeypatch, per_user=1, everyone=0)
    monkeypatch.setattr(deepseek, "chat", _fake_chat)
    monkeypatch.setattr(deepseek, "stream", _fake_stream)

    assert client.post("/api/chat", json={"message": "one"}).status_code == 200
    # Same user, same minute: the streamed path spends from the same bucket.
    assert (
        client.post(
            "/api/chat/stream",
            json={"message": "two"},
        ).status_code
        == 429
    )


def test_the_shared_budget_caps_everyone(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_limits(monkeypatch, per_user=0, everyone=1)
    monkeypatch.setattr(deepseek, "chat", _fake_chat)

    assert client.post("/api/chat", json={"message": "one"}).status_code == 200

    api.dependency_overrides[current_user] = lambda: {"email": "other@example.com"}
    second = client.post("/api/chat", json={"message": "two"})

    # A second account is under its own limit but the budget is spent.
    assert second.status_code == 429


def test_a_zero_limit_turns_the_limiter_off(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_limits(monkeypatch, per_user=0, everyone=0)
    monkeypatch.setattr(deepseek, "chat", _fake_chat)

    for _ in range(5):
        assert client.post("/api/chat", json={"message": "hi"}).status_code == 200


def test_limiter_frees_a_slot_after_the_window() -> None:
    now = 0.0
    limiter = ratelimit.Limiter(2, window=60.0, clock=lambda: now)

    assert limiter.retry_after("a") == 0.0
    assert limiter.retry_after("a") == 0.0
    assert limiter.retry_after("a") == pytest.approx(60.0)
    assert limiter.retry_after("b") == 0.0  # keys are independent

    now = 60.0
    assert limiter.retry_after("a") == 0.0


def test_security_headers_present(client: TestClient) -> None:
    headers = client.get("/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["permissions-policy"] == "geolocation=(), microphone=(), camera=()"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_hsts_only_over_https(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "strict-transport-security" not in client.get("/health").headers

    monkeypatch.setenv("APP_BASE_URL", "https://zuchat.test")
    assert "strict-transport-security" in client.get("/health").headers


def test_docs_serve_by_default(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_docs_disabled_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_DOCS", "false")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-0000000000000000")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    get_settings.cache_clear()
    with TestClient(create_app()) as fresh:
        assert fresh.get("/docs").status_code == 404
        assert fresh.get("/openapi.json").status_code == 404
