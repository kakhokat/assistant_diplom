from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from typing import Callable
from typing import Iterable


def normalize_for_match(value: str) -> str:
    cleaned = re.sub(r'[^\w\s]+', ' ', value.lower().replace('ё', 'е'))
    return ' '.join(cleaned.split())


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_for_match(left), normalize_for_match(right)).ratio()


def pick_best_candidate(
    query: str,
    items: Iterable[dict[str, Any]],
    value_getter: Callable[[dict[str, Any]], str],
) -> dict[str, Any] | None:
    best_item: dict[str, Any] | None = None
    best_score = -1.0
    normalized_query = normalize_for_match(query)

    for item in items:
        value = value_getter(item) or ''
        normalized_value = normalize_for_match(value)
        score = similarity(query, value)
        if normalized_query and normalized_value:
            if normalized_query == normalized_value:
                score += 2.0
            elif normalized_query in normalized_value:
                score += 0.7
            elif normalized_value in normalized_query:
                score += 0.4
        if score > best_score:
            best_item = item
            best_score = score

    return best_item
