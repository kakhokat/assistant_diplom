from contextlib import asynccontextmanager
import logging

import httpx
import redis.exceptions as redis_exc
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, ORJSONResponse
from redis.asyncio import Redis

from core.settings import settings
from domain.models import (
    AskRequest,
    AssistantFeedbackRequest,
    AssistantFeedbackResponse,
    AssistantResponse,
)
from services.assistant import AssistantService, build_assistant_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = httpx.AsyncHTTPTransport(retries=2)
    client = httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, transport=transport
    )
    session_redis = Redis.from_url(
        settings.ASSISTANT_SESSION_REDIS_URL,
        encoding="utf-8",
        decode_responses=False,
    )
    app.state.http_client = client
    app.state.session_redis = session_redis
    app.state.assistant_service = build_assistant_service(client, session_redis)
    try:
        yield
    finally:
        await session_redis.aclose()
        await client.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=settings.DOCS_URL,
    openapi_url=settings.OPENAPI_URL,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


@app.exception_handler(redis_exc.RedisError)
async def redis_error_handler(_, exc: redis_exc.RedisError):
    logger.exception("Assistant redis dependency error", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Assistant redis dependency is unavailable",
            "reason": "temporary unavailable",
        },
    )


@app.get("/assistant/health", tags=["assistant"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


def get_assistant_service(request: Request) -> AssistantService:
    return request.app.state.assistant_service


async def require_authorized_user(
    service: AssistantService = Depends(get_assistant_service),
    authorization: str | None = Header(default=None),
) -> dict:
    return await service.auth_client.me(authorization)


@app.post("/assistant/api/v1/ask", response_model=AssistantResponse, tags=["assistant"])
async def ask(
    payload: AskRequest,
    authorization: str | None = Header(default=None),
    service: AssistantService = Depends(get_assistant_service),
):
    return await service.handle_query(payload.query, authorization, payload.session_id)


@app.post(
    "/assistant/api/v1/feedback",
    response_model=AssistantFeedbackResponse,
    tags=["assistant"],
)
async def feedback(
    payload: AssistantFeedbackRequest,
    service: AssistantService = Depends(get_assistant_service),
    _current_user: dict = Depends(require_authorized_user),
):
    return await service.submit_feedback(payload)


@app.get("/assistant/api/v1/feed", tags=["assistant"])
async def public_feed(
    limit: int = Query(default=8, ge=1, le=20),
    authorization: str | None = Header(default=None),
    service: AssistantService = Depends(get_assistant_service),
):
    return await service.public_feed(limit, authorization)


@app.get("/assistant/api/v1/search", tags=["assistant"])
async def public_search(
    query: str = Query(min_length=1, max_length=200),
    authorization: str | None = Header(default=None),
    service: AssistantService = Depends(get_assistant_service),
):
    return await service.public_search(query, authorization)
