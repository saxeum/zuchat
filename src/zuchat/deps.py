"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends

from zuchat.config import Settings, get_settings


def deepseek_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Return the DeepSeek key from the environment."""
    return settings.deepseek_api_key.get_secret_value()
