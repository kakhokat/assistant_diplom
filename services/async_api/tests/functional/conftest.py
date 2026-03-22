import os

import httpx
import pytest

from ..utils.wait_for import wait_http

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")


@pytest.fixture(scope="session", autouse=True)
def wait_api():
    wait_http(f"{API_BASE}/api/openapi.json", timeout=120)


@pytest.fixture()
def client():
    return httpx.Client(base_url=API_BASE, timeout=10)
