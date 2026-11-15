"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings read from environment variables and an optional `.env` file."""

    # `extra="ignore"`: .env may carry tooling vars this app doesn't declare.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: SecretStr

    # Spend controls. The rate limits bound bursts; the token budgets bound the
    # bill, because one long prompt can cost more than hundreds of short ones.
    # 0 disables any individual control.
    max_output_tokens: int = 1024
    rate_limit_per_minute: int = 10
    rate_limit_global_per_minute: int = 60
    max_concurrent_per_user: int = 1
    max_concurrent_total: int = 8
    token_budget_per_day: int = 100_000
    token_budget_global_per_day: int = 1_000_000

    @field_validator("deepseek_api_key")
    @classmethod
    def _strip_whitespace(cls, value: SecretStr) -> SecretStr:
        """Reject blanks; trim newlines (Secrets Manager values often have one)."""
        key = value.get_secret_value().strip()
        if not key:
            msg = "DEEPSEEK_API_KEY is empty"
            raise ValueError(msg)
        return SecretStr(key)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loading them on first use."""
    # model_validate() applies the same settings sources as Settings(), without
    # the generated __init__ signature type checkers see as requiring fields.
    return Settings.model_validate({})
