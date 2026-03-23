import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _setup_test_env() -> None:
    # ВАЖНО: выставляем env ДО импортов app/db, чтобы настройки считались правильно
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["MONGO_DB"] = "ugc_test"

    # Длинный секрет, чтобы не ловить ограничения на длину
    os.environ["JWT_SECRET"] = "test-secret-please-make-it-at-least-32-bytes-long"
    os.environ["JWT_ALGORITHM"] = "HS256"

    # Если в приложении включат проверки iss/aud — оставляем опционально
    os.environ.setdefault("JWT_ISSUER", "")
    os.environ.setdefault("JWT_AUDIENCE", "")


_setup_test_env()

import jwt  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from httpx import AsyncClient  # noqa: E402

from services.ugc_api.app.db import close_client  # noqa: E402
from services.ugc_api.app.db import get_client  # noqa: E402
from services.ugc_api.app.main import app  # noqa: E402


def _make_token(user_id: str) -> str:
    secret = os.environ["JWT_SECRET"]
    alg = os.environ.get("JWT_ALGORITHM", "HS256")

    payload: dict[str, Any] = {"sub": user_id, "exp": int(time.time()) + 3600}

    iss = os.environ.get("JWT_ISSUER", "")
    aud = os.environ.get("JWT_AUDIENCE", "")
    if iss:
        payload["iss"] = iss
    if aud:
        payload["aud"] = aud

    return jwt.encode(payload, secret, algorithm=alg)


@pytest.fixture(autouse=True)
async def _clean_test_db():
    """
    Гарантирует изоляцию: после каждого теста база ugc_test очищается.
    """
    client = get_client()
    await client.admin.command("ping")
    yield
    await client.drop_database(os.environ["MONGO_DB"])
    await close_client()


@pytest.fixture()
def ids() -> dict[str, Any]:
    return {"user_id": "test_user", "film_id": "test_film"}


@pytest.fixture()
async def client(ids):
    token = _make_token(ids["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=headers,
    ) as ac:
        yield ac
