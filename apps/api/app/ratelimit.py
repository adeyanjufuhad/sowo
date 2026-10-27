"""Rate limits for the routes anyone on the internet can reach: sign-up and sign-in, and the webhooks.

The counters live in this process's memory, so with several replicas each one enforces its own limit. That still
stops a single client from hammering one instance, which is what these are for; a shared limit would need Redis (or
the database, which would keep a serverless Postgres awake), and the host's own edge limits are the place for more.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings, get_settings

WINDOW_SECONDS = 60.0
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60.0


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic, max_keys: int = 20_000) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._hits: dict[str, tuple[float, deque[float]]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, window: float, now: float) -> deque[float]:
        entry = self._hits.get(key)
        if entry is None:
            hits: deque[float] = deque()
            self._hits[key] = (window, hits)
            if len(self._hits) > self._max_keys:
                self._sweep(now)
            return hits
        hits = entry[1]
        while hits and now - hits[0] >= window:
            hits.popleft()
        return hits

    def _sweep(self, now: float) -> None:
        """Forget idle keys; if that is not enough, the oldest ones, so a flood of new keys can't grow memory."""
        for key, (window, hits) in list(self._hits.items()):
            if not hits or now - hits[-1] >= window:
                del self._hits[key]
        while len(self._hits) > self._max_keys:
            del self._hits[next(iter(self._hits))]

    def retry_after(self, key: str, limit: int, window: float) -> float:
        """Seconds until `key` may act again, or 0 if it is under its limit. Records nothing."""
        with self._lock:
            now = self._clock()
            hits = self._recent(key, window, now)
            return 0.0 if len(hits) < limit else max(window - (now - hits[0]), 0.001)

    def record(self, key: str, window: float) -> None:
        with self._lock:
            now = self._clock()
            self._recent(key, window, now).append(now)

    def hit(self, key: str, limit: int, window: float) -> float:
        """Count one action. Returns 0 if it is allowed, else the seconds to wait (and the action is not counted)."""
        with self._lock:
            now = self._clock()
            hits = self._recent(key, window, now)
            if len(hits) >= limit:
                return max(window - (now - hits[0]), 0.001)
            hits.append(now)
            return 0.0

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def too_many_requests(retry_after: float, message: str = "Too many requests. Wait a moment and try again.") -> JSONResponse:
    seconds = max(1, math.ceil(retry_after))
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": message}},
        headers={"Retry-After": str(seconds)},
    )


def client_ip(scope: Scope, settings: Settings) -> str:
    """The caller's address. Behind a trusted proxy, CLIENT_IP_HEADER names the header that carries it."""
    if settings.client_ip_header:
        forwarded = Headers(scope=scope).get(settings.client_ip_header, "").split(",")[0].strip()
        if forwarded:
            return forwarded
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            settings = get_settings()
            rule = self._rule(scope, settings) if settings.rate_limit_enabled else None
            if rule is not None:
                bucket, limit = rule
                wait = limiter.hit(f"{bucket}:{client_ip(scope, settings)}", limit, WINDOW_SECONDS)
                if wait:
                    await too_many_requests(wait)(scope, receive, send)
                    return
        await self.app(scope, receive, send)

    @staticmethod
    def _rule(scope: Scope, settings: Settings) -> tuple[str, int] | None:
        path = scope["path"]
        if scope["method"] == "POST" and path in ("/auth/login", "/auth/signup"):
            return "auth", settings.rate_limit_auth_per_minute
        if path.startswith("/webhooks/"):
            return "webhooks", settings.rate_limit_webhooks_per_minute
        return None
