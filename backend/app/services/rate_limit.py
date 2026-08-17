"""Hand-rolled in-memory sliding-window rate limiter — the right amount of engineering for a
single-process app with no Redis in this stack. Originally scoped to the AI Insights module's
`/interpret` and `/assistant` endpoints (per-authenticated-user, via `rate_limiter()`); the auth
module's `forgot-password` endpoint is pre-auth (no `current_user` yet), so it uses the plain
`check_email_rate_limit()` function below instead, sharing the same sliding-window core.

Resets on process restart and is NOT shared across multiple worker processes — documented here
rather than presented as production-grade; a real multi-worker deployment would need a shared
store (Redis, etc.) instead.
"""

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, status

from app.deps import get_current_user
from app.models.user import User

DEFAULT_LIMIT = 10
DEFAULT_WINDOW_SECONDS = 60

_request_log: dict[tuple[str, str | int], list[float]] = defaultdict(list)


def _check_and_record(key: tuple[str, str | int], limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    window_start = now - window_seconds
    recent = [t for t in _request_log[key] if t >= window_start]
    if len(recent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {limit} requests per {window_seconds} seconds.",
        )
    recent.append(now)
    _request_log[key] = recent


def rate_limiter(bucket: str, limit: int = DEFAULT_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS):
    """Returns a FastAPI dependency enforcing `limit` requests per `window_seconds` per
    (bucket, user_id). `bucket` keeps independent limits per endpoint (e.g. "assistant" vs.
    "interpret") in the same module-level store from colliding with each other."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        _check_and_record((bucket, current_user.id), limit, window_seconds)
        return current_user

    return _check


def check_email_rate_limit(bucket: str, email: str, limit: int = 3, window_seconds: int = 900) -> None:
    """Plain (non-`Depends`) rate limiter for pre-auth endpoints keyed by a submitted email
    address rather than an authenticated user id — e.g. `forgot-password`. Called directly from
    inside the route body, since the email only exists in the parsed request body, not in a path/
    query parameter a `Depends` could see. Keyed on the lowercased email; does not (and, with no
    IP plumbing anywhere in this codebase, cannot) stop an attacker who rotates target addresses —
    it only stops repeated requests against the *same* address."""
    _check_and_record((bucket, email.lower()), limit, window_seconds)


def reset_rate_limits() -> None:
    """Test-only helper — clears all in-memory rate-limit state between tests."""
    _request_log.clear()
