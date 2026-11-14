"""Tests for the Zuchat HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from zuchat import deepseek
from zuchat.config import get_settings
from zuchat.main import api, deepseek_api_key

if TYPE_CHECKING:
    from collections.abc import Iterator

TEST_API_KEY = "test-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Hermetic client: fake key in the environment, dependency overridden."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    get_settings.cache_clear()
    api.dependency_overrides[deepseek_api_key] = lambda: TEST_API_KEY
    yield TestClient(api)
    api.dependency_overrides.clear()
    get_settings.cache_clear()


def test_index(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "hello world"}


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


def test_models_uses_configured_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_models(api_key: str) -> list[dict[str, str]]:
        seen["api_key"] = api_key
        return [{"id": "deepseek-chat"}]

    monkeypatch.setattr(deepseek, "models", fake_models)

    response = client.get("/models")

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

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "hello back"}
    assert seen == {"api_key": TEST_API_KEY, "message": "hello"}
