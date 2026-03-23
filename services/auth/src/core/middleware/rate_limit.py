from __future__ import annotations

import time

import redis.exceptions as redis_exc
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool,
        max_requests: int,
        window_seconds: int,
        fail_open: bool,
        exclude_paths: set[str] | None = None,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fail_open = fail_open
        self.exclude_paths = exclude_paths or set()

    @staticmethod
    def _client_key(request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        return ip

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        if request.url.path in self.exclude_paths:
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            if self.fail_open:
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Rate limiter unavailable"},
            )

        ident = self._client_key(request)
        now = int(time.time())
        window = now // self.window_seconds
        key = f"ratelimit:{ident}:{window}"

        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, self.window_seconds + 1)
        except redis_exc.RedisError:
            if self.fail_open:
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Rate limiter unavailable"},
            )

        reset_ts = (window + 1) * self.window_seconds
        remaining = max(self.max_requests - int(current), 0)

        if int(current) > self.max_requests:
            resp = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
            resp.headers["X-RateLimit-Limit"] = str(self.max_requests)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(reset_ts)
            return resp

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response
