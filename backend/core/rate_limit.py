"""
backend/core/rate_limit.py
===========================
Simple in-memory rate limiter implemented as FastAPI middleware.
No external library dependency — avoids the slowapi/passlib test interference.

Strategy: sliding window counter per (IP, endpoint) pair.
- Login:    10 attempts per minute per IP
- Register: 5  attempts per minute per IP
- Global:   300 requests per minute per IP (anti-DDoS)

Thread-safety: Python's GIL makes dict operations safe for asyncio;
for multi-process production use Redis instead.

Tests: rate limiting is bypassed when ENV=test (set via environment).
"""

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ── Per-route limits ──────────────────────────────────────────────────────────
ROUTE_LIMITS: dict[str, tuple[int, int]] = {
    # (path_suffix, method): (max_requests, window_seconds)
    "/auth/login":    (10, 60),
    "/auth/register": (5,  60),
}
GLOBAL_LIMIT = (300, 60)  # 300 req/min per IP

# ── In-memory sliding window ──────────────────────────────────────────────────
_windows: dict[str, deque] = defaultdict(deque)


def _is_rate_limited(key: str, max_req: int, window: int) -> bool:
    """Returns True if the key has exceeded max_req in the last window seconds."""
    now = time.monotonic()
    q = _windows[key]
    # Expire old entries
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_req:
        return True
    q.append(now)
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter middleware.
    Disabled automatically when ENV=test to keep pytest unaffected.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import os
        if os.getenv("ENV", "development").lower() == "test":
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method

        # Route-specific limit
        for route_suffix, (max_req, window) in ROUTE_LIMITS.items():
            if path.endswith(route_suffix) and method == "POST":
                key = f"route:{ip}:{route_suffix}"
                if _is_rate_limited(key, max_req, window):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": (
                                f"Too many requests. "
                                f"Limit: {max_req} per {window}s. "
                                "Please wait and try again."
                            )
                        },
                        headers={"Retry-After": str(window)},
                    )

        # Global limit
        global_key = f"global:{ip}"
        max_g, win_g = GLOBAL_LIMIT
        if _is_rate_limited(global_key, max_g, win_g):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down."},
                headers={"Retry-After": str(win_g)},
            )

        return await call_next(request)
