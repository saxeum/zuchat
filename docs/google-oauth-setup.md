# Creating the Google OAuth client (zuchat)

Step-by-step companion to the Authentication section of the README. Modelled on
the equivalent doc in `numbat`, which uses Better Auth's Google provider; the
console steps are identical, only the callback path differs.

- **Redirect URIs are exact — no wildcards.** They must match character for
  character, including scheme, port, and path.
- Scopes are **non-sensitive** (`openid`, `email`, `profile`), so no Google
  verification review is required.
- The app can stay in **Testing**; up to 100 test users can sign in.

## 1. Project

<https://console.cloud.google.com/> → project selector → **New project**
(e.g. `zuchat`) → **Create**, then select it.

## 2. Consent screen

**APIs & Services → OAuth consent screen**

1. **User type:** External → **Create**
2. **App name:** `zuchat`; support email and developer contact: yours
3. **Scopes:** add `openid`, `email`, `profile`
4. **Test users:** add the Google account you will sign in with
5. Save (leave it in Testing)

## 3. OAuth client

**APIs & Services → Credentials → Create credentials → OAuth client ID**

- **Application type:** Web application
- **Name:** `zuchat web`
- **Authorised redirect URIs** — add the ones you use, exactly:

| Where the app runs | Redirect URI |
| --- | --- |
| `make dev` (:8000) | `http://localhost:8000/auth` |
| container (:8001) | `http://localhost:8001/auth` |
| ECS/ALB with a domain | `https://<your-domain>/auth` |

- Copy the **Client ID** and **Client secret**

## 4. Wire the values in

Download the client JSON from the console (**Credentials → your client → Download
JSON**) and save it as `~/.config/zuchat/google-oauth.json` (`chmod 600`). The
Makefile reads `client_id` and `client_secret` straight out of it:

```bash
mv ~/Downloads/client_secret_*.json ~/.config/zuchat/google-oauth.json
chmod 600 ~/.config/zuchat/google-oauth.json

openssl rand -base64 32 > ~/.config/zuchat/session-secret
chmod 600 ~/.config/zuchat/session-secret
```

Optional overrides (environment, or the same file names):

| Variable | Default |
| --- | --- |
| `ALLOWED_EMAILS` | empty = any Google account |
| `APP_BASE_URL` | `http://localhost:8000` |

Check what was picked up without printing secrets: `make oauth-status`. Naming differs from numbat only in the app's own
variables:

| numbat | zuchat |
| --- | --- |
| `BETTER_AUTH_SECRET` | `SESSION_SECRET` |
| `BETTER_AUTH_URL` | `APP_BASE_URL` |
| `/api/auth/callback/google` | `/auth` |

## 5. Verify

```bash
make dev
# open http://localhost:8000/login, sign in, then:
curl -s -b /tmp/jar -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' -d '{"message":"hi"}'
```

`ALLOWED_EMAILS` is the lock: with it empty, any Google account can spend your
DeepSeek credits.

## Notes for ECS

- `APP_BASE_URL` must be the public HTTPS origin; the session cookie flips to
  `Secure` automatically.
- The ALB DNS name (`*.elb.amazonaws.com`) is a valid redirect URI, but it
  changes if the ALB is recreated — use a custom domain before pointing ECS at
  it, or expect occasional `redirect_uri_mismatch`.
- Keep `GOOGLE_CLIENT_SECRET` in Secrets Manager, not in the task definition.
