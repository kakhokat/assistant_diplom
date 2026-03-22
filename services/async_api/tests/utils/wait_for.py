import time

import httpx


def wait_http(url: str, timeout: int = 60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"Service not healthy: {url}")
