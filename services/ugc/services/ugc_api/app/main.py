from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import TypedDict

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from .constants import (
    ENV_GIT_SHA,
    ENV_SENTRY_DSN,
    ENV_SENTRY_ENVIRONMENT,
    ENV_SENTRY_PROFILES_SAMPLE_RATE,
    ENV_SENTRY_TRACES_SAMPLE_RATE,
)
from .db import close_client, get_client, get_db
from .repositories.bookmarks_repo import BookmarksRepo
from .repositories.likes_repo import LikesRepo
from .repositories.reviews_repo import ReviewsRepo
from .routers.bookmarks import router as bookmarks_router
from .routers.likes import router as likes_router
from .routers.reviews import router as reviews_router
from .settings import settings

logger = logging.getLogger("ugc_api")


class Repos(TypedDict):
    likes: LikesRepo
    bookmarks: BookmarksRepo
    reviews: ReviewsRepo


def _init_sentry(service_name: str) -> None:
    dsn = os.getenv(ENV_SENTRY_DSN, "").strip()
    if not dsn:
        logger.info("Sentry DSN is empty: Sentry is disabled")
        return

    traces_sample_rate = float(os.getenv(ENV_SENTRY_TRACES_SAMPLE_RATE, "0.1"))
    profiles_sample_rate = float(os.getenv(ENV_SENTRY_PROFILES_SAMPLE_RATE, "0.0"))
    environment = os.getenv(ENV_SENTRY_ENVIRONMENT, settings.app_env)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        release=os.getenv(ENV_GIT_SHA) or None,
        server_name=service_name,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_sentry("services/ugc_api")

    client = get_client()
    await client.admin.command("ping")

    db = get_db()

    repos: Repos = {
        "likes": LikesRepo(db),
        "bookmarks": BookmarksRepo(db),
        "reviews": ReviewsRepo(db),
    }

    # Ensure DB indexes exist (idempotent).
    await repos["likes"].ensure_indexes()
    await repos["bookmarks"].ensure_indexes()
    await repos["reviews"].ensure_indexes()

    app.state.repos = repos  # type: ignore[attr-defined]

    try:
        yield
    finally:
        await close_client()


app = FastAPI(
    title="UGC CRUD API (MongoDB)",
    version="1.0.0",
    lifespan=lifespan,
    # Allows running behind reverse proxy under a prefix (e.g. /ugc).
    root_path=settings.root_path,
)

app.add_middleware(SentryAsgiMiddleware)

# Routers
app.include_router(likes_router)
app.include_router(bookmarks_router)
app.include_router(reviews_router)

# Prometheus
app.mount("/metrics", make_asgi_app())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    sentry_sdk.capture_exception(exc)
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


_is_prod = settings.app_env.lower() in {"prod", "production"}

if not _is_prod:

    @app.get("/debug-sentry", include_in_schema=False)
    async def debug_sentry():
        raise RuntimeError("Sentry test exception from services/ugc_api")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}
