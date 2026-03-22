from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "x-request-id"):
        super().__init__(app)
        self.header_name = header_name.lower()

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(self.header_name) or uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            span = trace.get_current_span()
            if span:
                span.set_attribute("request.id", rid)
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        response.headers[self.header_name] = rid
        return response
