# zuchat

A FastAPI chat app backed by the DeepSeek API, running in Docker.

## Bootstrap

One file, outside the repo:

```
~/.config/zuchat/deepseek.token     your DeepSeek API key
```

The Makefile reads it into `DEEPSEEK_API_KEY` and exports it; Compose passes it
to the container.

## Quickstart

```bash
make up      # build + start on http://127.0.0.1:8001
make smoke   # -> reply: pong  PASS
make chat MSG="hello"
make down
```

## Targets

| Target | Does |
| --- | --- |
| `make up` | build and start the app container |
| `make down` | stop it |
| `make smoke` | end-to-end check |
| `make dev` | app on :8000 with `--reload` (host venv, key from the file) |
| `make chat MSG="…"` | one round-trip against the container (:8001) |
| `make smoke` | end-to-end check of the container |
| `make chat-local` | same, against the local dev server (:8000) |
| `make smoke-local` | end-to-end check of :8000 |
| `make test` | unit tests, local venv, no network |
| `make lint` | ruff |
| `make image` | build the image |

## Endpoints

| Path | Use |
| --- | --- |
| `GET /health` | liveness (ALB target group / ECS container health check) |
| `GET /ready` | readiness: 503 until the API key is configured |
| `GET /models` | DeepSeek model list |
| `POST /chat` | `{"message": "..."}` → `{"reply": "..."}` |

## Authentication

`/chat` requires a Google account. Everything else stays public.

Download the OAuth client JSON from the Google console (**Credentials → your
client → Download JSON**) and put it here:

```bash
mv ~/Downloads/client_secret_*.json ~/.config/zuchat/google-oauth.json
openssl rand -base64 32 > ~/.config/zuchat/session-secret
chmod 600 ~/.config/zuchat/google-oauth.json ~/.config/zuchat/session-secret
make oauth-status      # masked confirmation
```

The Makefile extracts `client_id`/`client_secret` from the JSON. `ALLOWED_EMAILS`
and `APP_BASE_URL` are optional overrides (environment or the same shell).

Register the redirect URI in the Google console:

| Where the app runs | Authorised redirect URI |
| --- | --- |
| `make dev` (:8000) | `http://localhost:8000/auth` |
| container (:8001) | `http://localhost:8001/auth` |

Full console walkthrough: [docs/google-oauth-setup.md](docs/google-oauth-setup.md).

Then open <http://localhost:8000/login>, sign in, and `/chat` accepts the
session cookie. `ALLOWED_EMAILS` is the lock: leave it empty and *any* Google
account can spend your DeepSeek credits; set it to your address and everyone
else gets 403. `/logout` clears the session.

## Notes

- The key is an environment variable inside the container: `DEEPSEEK_API_KEY`.
- `Settings` requires it; the app refuses to start without it.
- To use a different key file: `make up KEY_FILE=/path/to/file`.

## License

MIT — see [LICENSE](LICENSE).

## Files

| Path | Purpose |
| --- | --- |
| `compose.yaml` | the app service |
| `Dockerfile` | app image |
| `src/zuchat/config.py` | settings (`deepseek_api_key`) |
| `src/zuchat/main.py` | FastAPI app |
| `src/zuchat/deepseek.py` | DeepSeek client |
| `scripts/chat.sh`, `scripts/smoke.sh` | HTTP helpers |
