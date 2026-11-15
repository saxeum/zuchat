"""Operations endpoints: public, because the load balancer calls them."""

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from zuchat.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: touches no dependencies (ALB target group / ECS health check).

    Async on purpose: sync handlers run in the shared thread pool, which
    streaming replies also occupy, so a burst of chats could otherwise queue the
    health check behind them and get the task replaced.
    """
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "not ready"}})
async def ready() -> dict[str, str]:
    """Readiness: 503 until the API key is configured. Never calls DeepSeek.

    Async for the same reason as `health`: the settings are cached after the
    first load, so this does no blocking work.
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
