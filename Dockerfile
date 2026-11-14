# App image: the DeepSeek key arrives as an environment variable.
FROM python:3.14-slim

# Pin uv rather than relying on a floating image tag.
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Dependency layer first: it only changes when the lockfile changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 8000
# Trust X-Forwarded-* from the ALB so request.url reflects https.
CMD ["uvicorn", "zuchat.main:api", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
