"""JSON API: chat, models, and the current user for the UI."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from zuchat import deepseek
from zuchat.auth import current_user
from zuchat.config import get_settings
from zuchat.deps import deepseek_api_key

router = APIRouter()


class ChatRequest(BaseModel):
    """Capped so a public endpoint cannot be used to send megabyte prompts."""

    message: str = Field(min_length=1, max_length=4000)


@router.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness: touches no dependencies (ALB target group / ECS health check)."""
    return {"status": "ok"}


@router.get("/ready", tags=["ops"], responses={503: {"description": "not ready"}})
def ready() -> dict[str, str]:
    """Readiness: 503 until the API key is configured. Never calls DeepSeek."""
    try:
        key = get_settings().deepseek_api_key.get_secret_value()
    except ValidationError:
        key = ""
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="deepseek api key is not configured",
        )
    return {"status": "ready"}


@router.get("/me")
def me(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
    """Who the session belongs to; 401 when signed out."""
    return user


@router.get("/models")
def models(
    api_key: Annotated[str, Depends(deepseek_api_key)],
    _user: Annotated[dict[str, str], Depends(current_user)],
) -> list[dict[str, object]]:
    return deepseek.models(api_key)


@router.post("/chat")
def chat(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
    _user: Annotated[dict[str, str], Depends(current_user)],
) -> dict[str, str]:
    return {"reply": deepseek.chat(api_key, request.message)}
