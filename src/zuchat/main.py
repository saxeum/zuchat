"""ASGI entrypoint: `uvicorn zuchat.main:api`."""

import uvicorn

from zuchat.app import api

__all__ = ["api"]


def main() -> None:
    uvicorn.run("zuchat.main:api", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
