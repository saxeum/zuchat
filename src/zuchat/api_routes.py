"""Authenticated JSON API. Everything under /api requires a session."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from zuchat import deepseek
from zuchat.auth import current_user
from zuchat.deps import deepseek_api_key

# One dependency at the router level: every /api route is authenticated, and a
# new route cannot forget it.
router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(current_user)])


class ChatRequest(BaseModel):
    """Capped so a public endpoint cannot be used to send megabyte prompts."""

    message: str = Field(min_length=1, max_length=4000)


@router.get("/me")
def me(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
    """Who the session belongs to."""
    return user


@router.get("/models")
def models(
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> list[dict[str, object]]:
    return deepseek.models(api_key)


@router.post("/chat")
def chat(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> dict[str, str]:
    return {"reply": deepseek.chat(api_key, request.message)}
