"""Token-bucket rate limiting for the public API.

The point is narrow: `/api/profiles` hands back the whole board in one
response because the map needs every pin at once, so the thing worth limiting
is how *often* someone can ask, not how much they get. That stops a casual
re-scrape from rebuilding the dataset in a loop.

Deliberately in-process. This runs as a single uvicorn worker, and state that
resets on restart is the honest trade for zero dependencies. Multiple workers,
or a determined scraper on rotating IPs, need the limit at the reverse proxy
instead — see README.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Allows `burst` requests immediately, then refills at `rpm` per minute."""

    #: Beyond this many tracked clients, drop the ones that have refilled
    #: anyway — otherwise the dict is an unbounded leak on a long-lived process.
    _MAX_KEYS = 10_000

    def __init__(
        self,
        app,
        *,
        rpm: int,
        burst: int,
        prefix: str = "/api",
        trust_proxy: bool = False,
    ) -> None:
        super().__init__(app)
        self.rpm = rpm
        self.rate = rpm / 60.0
        self.burst = float(burst)
        self.prefix = prefix
        self.trust_proxy = trust_proxy
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        # X-Forwarded-For is only trustworthy behind a proxy we control, and a
        # client can send any value it likes. Deployed behind Render's edge the
        # socket address is the *proxy*, so without this every visitor shares
        # one bucket and the first few page loads 429 the rest of the world.
        # The left-most entry is the original client; the proxy appends its own.
        if self.trust_proxy:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _prune(self, now: float) -> None:
        if len(self._buckets) < self._MAX_KEYS:
            return
        refilled_after = self.burst / self.rate
        for key in [
            k for k, b in self._buckets.items() if now - b.updated > refilled_after
        ]:
            del self._buckets[key]

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith(self.prefix):
            return await call_next(request)

        now = time.monotonic()
        key = self._client_key(request)

        with self._lock:
            self._prune(now)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = _Bucket(self.burst, now)
            bucket.tokens = min(
                self.burst, bucket.tokens + (now - bucket.updated) * self.rate
            )
            bucket.updated = now

            if bucket.tokens < 1.0:
                retry_after = max(1, int((1.0 - bucket.tokens) / self.rate) + 1)
                return JSONResponse(
                    {"detail": "Too many requests — slow down."},
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.rpm),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            bucket.tokens -= 1.0
            remaining = int(bucket.tokens)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
