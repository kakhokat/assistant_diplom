import os

import pytest

from fastapi.testclient import TestClient

# ВАЖНО: до импорта main/settings/db
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OTEL_ENABLED", "false")

# ✅ чтобы тесты были повторяемыми между прогонами pytest
os.environ.setdefault("DB_RESET_ON_STARTUP", "true")

# Если ты запускаешь pytest на Windows-хосте (а Postgres/Redis в docker-compose),
# к ним ходим через localhost:port-mapping, а не hostname "postgres".
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "auth_db")
os.environ.setdefault("DB_USER", "auth_user")
os.environ.setdefault("DB_PASSWORD", "auth_password")

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Общий TestClient для функциональных тестов.
    При создании поднимется lifespan (init БД, Redis и т.п.).
    """
    with TestClient(app) as c:
        yield c
