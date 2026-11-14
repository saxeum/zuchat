from collections.abc import AsyncIterator  # noqa: TC003 - evaluated at runtime
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ValidationError

from zuchat import deepseek
from zuchat.config import Settings, get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast: a task without the key should die, not serve 500s."""
    get_settings()
    yield


api = FastAPI(title="Zuchat", version="0.1.0", lifespan=lifespan)


def deepseek_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """FastAPI dependency: the DeepSeek key from the environment."""
    return settings.deepseek_api_key.get_secret_value()


class ChatRequest(BaseModel):
    message: str


@api.get("/")
def index() -> dict[str, str]:
    return {"message": "hello world"}


@api.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness: the process is up. Touches no dependencies.

    Used by the ALB target group / ECS container health check.
    """
    return {"status": "ok"}


@api.get("/ready", tags=["ops"], responses={503: {"description": "not ready"}})
def ready() -> dict[str, str]:
    """Readiness: this task can serve traffic.

    Checks the one thing that would make requests fail: the API key. It does
    not call DeepSeek, so it stays cheap and cannot be rate limited.
    """
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


@api.get("/models")
def get_models(
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> list[dict[str, object]]:
    return deepseek.models(api_key)


@api.post("/chat")
def chat(
    request: ChatRequest,
    api_key: Annotated[str, Depends(deepseek_api_key)],
) -> dict[str, str]:
    reply = deepseek.chat(api_key, request.message)
    return {"reply": reply}


def main() -> None:
    uvicorn.run("zuchat.main:api", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
