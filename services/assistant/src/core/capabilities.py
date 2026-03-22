from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def get_capabilities() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / 'config' / 'capabilities.json'
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def get_supported_intents() -> set[str]:
    payload = get_capabilities()
    return {item['name'] for item in payload.get('intents', [])}
