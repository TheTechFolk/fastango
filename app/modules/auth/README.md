# Auth

The template's one reference module, and infrastructure rather than a demo —
every project needs login, so this ships complete.

## Routes

| Method | Path | Auth |
|---|---|---|
| POST | `/public/api/v1/auth/register` | none (rate limited, closable via `REGISTRATION_ENABLED`) |
| POST | `/public/api/v1/auth/login` | none (rate limited) |
| POST | `/public/api/v1/auth/refresh` | refresh token in body (rate limited, rotates) |
| POST | `/public/api/v1/auth/logout` | refresh token in body (rate limited) |
| GET | `/private/api/v1/auth/me` | access token |

## The core/module split

    auth/utils.py     issues credentials  (hash, sign)
    core/security.py  verifies them       (decode, identify)

Decoding runs on every private request, so the auth middleware needs it — and
`core/` importing from a module would invert the dependency the registry rests
on. Delete this module and the app must still boot.

## Security properties worth not breaking

- **Login is timing-flat.** An unknown email still pays a bcrypt verification
  against `dummy_hash()`. Short-circuiting on "no such user" turns identical
  messages into an enumeration oracle via response time.
- **Registration never reads `role` from the body.** `RegisterSchema` does not
  expose it and the service hardcodes `RoleType.USER`.
- **A duplicate email is a `ValidationException` (400), not a 409.** A 409
  confirms the address is taken, which is what the generic message hides.
- **bcrypt runs in a thread.** ~300ms on the event loop is 300ms the worker
  serves nobody.
- **The refresh token carries no `role` claim.** The role is re-read from the
  record, so a demotion takes effect at the next refresh.
- **Refresh tokens are single-use.** `/refresh` revokes the token it redeems
  (by `jti`, in `revoked_token`), and `/logout` revokes the one it is given. A
  reused refresh token gets a 401 — that is what a stolen one looks like.
- **Access tokens are never looked up.** Revocation touches only `/refresh` and
  `/logout`, so private requests stay I/O-free. The cost: an access token
  outlives logout by up to `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (15 by default).
  Keep it short; instant revocation needs a per-request denylist (Redis).
