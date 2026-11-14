"""Operations endpoints: public, because the load balancer calls them."""

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from zuchat.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: touches no dependencies (ALB target group / ECS health check)."""
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "not ready"}})
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
