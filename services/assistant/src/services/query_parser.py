from __future__ import annotations

import re
from typing import Any

from core.text_tools import normalize_for_match


def normalize(value: str) -> str:
    return " " + normalize_for_match(value) + " "


def detect_intent(query: str) -> str:
    text = normalize(query)
    if any(token in text for token in ["заклад", "избранн"]):
        return "bookmarks"
    if any(token in text for token in ["посовет", "рекоменд"]) and any(
        token in text
        for token in ["актёр", "актер", "режисс", "автор", "фильмы с ", "фильмы от "]
    ):
        return "recommend_by_person"
    if any(token in text for token in ["посовет", "рекоменд"]) and any(
        token in text for token in ["любим", "предпочтен"]
    ):
        return "recommend_by_genre"
    if any(token in text for token in ["посовет", "рекоменд", "что посмотреть"]):
        return "recommend_general"
    if any(token in text for token in ["сколько фильмов"]):
        return "person_movie_count"
    if any(
        token in text
        for token in [
            "фильмограф",
            "какие фильмы у",
            "какие фильмы снял",
            "какие фильмы сняла",
            "что снял",
            "что сняла",
            "что еще снял",
            "что еще сняла",
            "фильмы с участием",
            "фильмы с акт",
            "фильмы с режисс",
            "фильмы режисс",
            "фильмы у ",
        ]
    ):
        return "person_filmography"
    if any(
        token in text
        for token in ["сколько длится", "длительность", "идет фильм", "идёт фильм"]
    ):
        return "film_duration"
    if any(
        token in text
        for token in [
            "кто режисс",
            "кто снял",
            "кто снимал",
            "кто поставил",
            "режиссер фильма",
            "режиссёр фильма",
            "автор фильма",
        ]
    ):
        return "film_director"
    if any(token in text for token in ["оценк", "рейтинг"]):
        return "film_rating"
    if any(token in text for token in ["жанр"]):
        return "film_genres"
    if any(
        token in text
        for token in [
            "о чем фильм",
            "о чём фильм",
            "о чем этот фильм",
            "о чём этот фильм",
            "а чем фильм",
            "а чем этот фильм",
            "про что фильм",
            "про что этот фильм",
            "расскажи про фильм",
            "что за фильм",
            "информация о фильме",
            "сводк",
            "описан",
            "сюжет",
            "кратко о фильме",
        ]
    ):
        return "film_overview"
    return "help"


def extract_film_title_with_context(query: str, session: dict[str, Any]) -> str:
    quoted = extract_quoted(query)
    if quoted:
        return quoted
    if looks_like_film_followup(query) and session.get("film_title"):
        return str(session["film_title"])
    tail = extract_tail(
        query,
        [
            r"(?:оценк[аи]?|рейтинг)[^\w]*(?:у|фильма)?\s+(.+)$",
            r"(?:кто\s+режисс[её]р\s+фильма|режисс[её]р\s+фильма|автор\s+фильма|кто\s+снял(?:\s+фильм)?|кто\s+снимал(?:\s+фильм)?|кто\s+поставил(?:\s+фильм)?)\s+(.+)$",
            r"(?:сколько\s+длится\s+фильм|длительность\s+фильма)\s+(.+)$",
            r"(?:жанр(?:ы)?\s+фильма|какие\s+жанры\s+у\s+фильма)\s+(.+)$",
            r"(?:(?:о|а)\s+ч[её]м\s+(?:этот\s+)?фильм|про\s+что\s+(?:этот\s+)?фильм|расскажи\s+про\s+фильм|что\s+за\s+фильм|(?:кратк\w*|коротк\w*)\s+сводк\w*\s+по\s+фильму|описан\w*\s+фильма|сюжет\w*\s+фильма|кратко\s+о\s+фильме|дай\s+(?:(?:кратк\w*|коротк\w*)\s+)?сводк\w*\s+по\s+фильму)\s+(.+)$",
        ],
    )
    if tail:
        return tail
    return ""


def extract_person_name_with_context(query: str, session: dict[str, Any]) -> str:
    quoted = extract_quoted(query)
    if quoted:
        return quoted
    if looks_like_person_followup(query) and session.get("person_name"):
        return str(session["person_name"])
    tail = extract_tail(
        query,
        [
            r"(?:сколько\s+фильмов\s+у|сколько\s+фильмов\s+снял|сколько\s+фильмов\s+сняла|какие\s+фильмы\s+у|какие\s+фильмы\s+снял|какие\s+фильмы\s+сняла|что(?:\s+еще)?\s+снял|что(?:\s+еще)?\s+сняла|фильмы\s+с\s+участием|посоветуй\s+фильмы\s+с)\s+(.+)$",
            r"фильмограф(?:ия|ию)\s+(?:режисс[её]ра\s+|акт[её]ра\s+|сценариста\s+)?(.+)$",
        ],
    )
    if tail:
        return tail
    return ""


def extract_quoted(query: str) -> str:
    for pattern in [r"«([^»]+)»", r'"([^"]+)"']:
        match = re.search(pattern, query)
        if match:
            return match.group(1).strip()
    return ""


def extract_tail(query: str, patterns: list[str]) -> str:
    cleaned = query.strip().rstrip("?.! ")
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip("?.! ")
    return ""


def looks_like_film_followup(query: str) -> bool:
    text = normalize(query)
    return (
        any(
            token in text
            for token in [
                " он",
                " него",
                " этот фильм",
                " этого фильма",
                " его ",
                " у него",
            ]
        )
        or text.startswith(" а сколько")
        or text.startswith(" а какие")
    )


def looks_like_person_followup(query: str) -> bool:
    text = normalize(query)
    return any(
        token in text
        for token in ["этот автор", "этот режиссер", "этот режиссёр", "у неё", "у нее"]
    ) or text.startswith(" а сколько")


def candidate_queries(primary: str, extras: list[str]) -> list[str]:
    seen: list[str] = []
    for item in [primary, *extras]:
        value = item.strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def extract_explicit_genre_hint(query: str) -> str:
    cleaned = normalize_for_match(query)
    synonym_map = {
        "спорт": "спорт",
        "спортив": "спорт",
        "драма": "драма",
        "драм": "драма",
        "комедия": "комедия",
        "комед": "комедия",
        "романтика": "романтика",
        "романт": "романтика",
        "фантастика": "фантастика",
        "фантаст": "фантастика",
        "детектив": "детектив",
    }
    for source, target in synonym_map.items():
        if source in cleaned:
            return target
    patterns = [
        r"в\s+жанре\s+([а-яё\- ]+)",
        r"жанра\s+([а-яё\- ]+)",
        r"жанр\s+([а-яё\- ]+)",
        r"из\s+([а-яё\- ]+)",
        r"([а-яё\- ]+)\s+фильмы",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""
