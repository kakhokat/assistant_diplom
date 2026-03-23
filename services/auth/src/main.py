from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, RedirectResponse
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.v1 import auth, oauth, roles, users
from core.bootstrap import ensure_bootstrap_admin
from core.logger import LOGGING
from core.middleware.rate_limit import RateLimitMiddleware
from core.middleware.request_id import RequestIdMiddleware
from core.settings import settings
from core.tracing import setup_tracing, shutdown_tracing
from db import postgres, redis as redis_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_db.redis = Redis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=False
    )
    app.state.redis = redis_db.redis

    async with postgres.startup_lock():
        await postgres.init_models(reset=(settings.APP_ENV == "test"))
        await ensure_bootstrap_admin()

    try:
        yield
    finally:
        shutdown_tracing(app)
        if redis_db.redis:
            await redis_db.redis.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=settings.DOCS_URL,
    openapi_url=settings.OPENAPI_URL,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# Tracing (Jaeger)
setup_tracing(app)

# Request ID (x-request-id)
app.add_middleware(RequestIdMiddleware, header_name=settings.REQUEST_ID_HEADER)

# Rate limit
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.RATE_LIMIT_ENABLED,
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    fail_open=settings.RATE_LIMIT_FAIL_OPEN,
    exclude_paths={settings.DOCS_URL, settings.OPENAPI_URL, "/"},
)

# Proxy headers
trusted = (
    ["*"]
    if settings.PROXY_TRUSTED_HOSTS.strip() == "*"
    else [h.strip() for h in settings.PROXY_TRUSTED_HOSTS.split(",") if h.strip()]
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)

# CORS
origins = (
    ["*"]
    if settings.CORS_ALLOW_ORIGINS.strip() == "*"
    else [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(roles.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1", tags=["oauth"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url=settings.DOCS_URL)


dictConfig(LOGGING)
