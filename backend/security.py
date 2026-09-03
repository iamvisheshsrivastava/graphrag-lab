"""
Minimal-viable auth + rate limiting for cost-sensitive endpoints (issue #2).

Design:
- API key is OPTIONAL. If the `API_KEY` env var is unset, `require_api_key`
  is a no-op and the app behaves exactly as it does today (open, matching
  the current public demo deployment). If `API_KEY` is set, callers must
  send a matching `X-API-Key` header on the guarded endpoints.
- Rate limiting is a simple in-memory fixed-window counter keyed by client
  IP, applied only to the endpoints that call OpenRouter (the actual
  cost-abuse vector the issue calls out) — not to cheap read endpoints.

NOTE: The rate limiter's state is a plain in-process dict. That's fine only
because this app runs as a single Render free-tier instance (no
--workers > 1, no horizontal scaling). If that ever changes, this needs to
move to a shared store (e.g. Redis) — see issue #6 for the related
multi-worker state problem.
"""

import os
import time
import logging
from collections import defaultdict

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: no-op if API_KEY is unset; otherwise requires a
    matching X-API-Key header."""
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


# ─── Rate limiting ──────────────────────────────────────────────────────────

RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))

# client_ip -> (window_start_epoch, count)
_buckets: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def _client_ip(request: Request) -> str:
    # Render sits behind a proxy; prefer the first hop of X-Forwarded-For
    # when present, falling back to the direct connection.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_llm(request: Request) -> None:
    """FastAPI dependency: fixed-window per-IP rate limit for endpoints that
    call OpenRouter. Not applied to cheap read endpoints (/health,
    /graph/current, etc.) — only to the actual cost-abuse vector."""
    ip = _client_ip(request)
    now = time.time()
    window_start, count = _buckets[ip]

    if now - window_start >= RATE_LIMIT_WINDOW_SECONDS:
        _buckets[ip] = (now, 1)
        return

    if count >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning("Rate limit exceeded for %s", ip)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: max {RATE_LIMIT_MAX_REQUESTS} requests "
                f"per {RATE_LIMIT_WINDOW_SECONDS}s on this endpoint. Try again shortly."
            ),
        )

    _buckets[ip] = (window_start, count + 1)
