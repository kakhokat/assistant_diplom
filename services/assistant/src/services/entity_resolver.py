from __future__ import annotations

import logging
import random
from typing import Any, Iterable

import httpx

from core.capabilities import get_capabilities
from core.text_tools import normalize_for_match, pick_best_candidate
from services.query_parser import candidate_queries, extract_explicit_genre_hint

logger = logging.getLogger(__name__)


async def prepare_film_cards(
    service: Any,
    items: list[dict[str, Any]],
    authorization: str | None,
) -> list[dict[str, Any]]:
    details_by_id: dict[str, dict[str, Any]] = {}
    if items:
        details = await load_film_details(
            service,
            [str(item.get("uuid")) for item in items if item.get("uuid")],
            authorization,
        )
        details_by_id = {
            str(item.get("uuid")): item for item in details if item.get("uuid")
        }

    prepared: list[dict[str, Any]] = []
    for item in items:
        film_id = str(item.get("uuid") or "")
        detail = details_by_id.get(film_id, {})
        genres = (
            await resolve_genre_names(service, detail.get("genre") or [], authorization)
            if detail
            else []
        )
        prepared.append(
            {
                **item,
                "uuid": item.get("uuid"),
                "title": item.get("title") or detail.get("title"),
                "original_title": item.get("original_title")
                or detail.get("original_title"),
                "imdb_rating": item.get("imdb_rating")
                if item.get("imdb_rating") is not None
                else detail.get("imdb_rating"),
                "genre": genres,
                "directors": detail.get("directors") or [],
                "description": detail.get("description"),
            }
        )
    return prepared


async def format_person_name_for_answer(
    service: Any, name: str, authorization: str | None
) -> str:
    try:
        candidates = await service._catalog_search_persons(name, authorization)
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        logger.warning("Failed to resolve person name %r: %s", name, exc)
        return name
    if not candidates:
        return name
    normalized = normalize_for_match(name)
    exact = next(
        (
            item
            for item in candidates
            if normalize_for_match(item.get("full_name", "")) == normalized
            or normalized
            in [normalize_for_match(alias) for alias in (item.get("aliases") or [])]
        ),
        candidates[0],
    )
    return str(exact.get("full_name") or name)


async def format_person_names_for_answer(
    service: Any, names: list[str], authorization: str | None
) -> list[str]:
    return [
        await format_person_name_for_answer(service, name, authorization)
        for name in names
    ]


def display_title(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    original_title = str(item.get("original_title") or "").strip()
    if (
        title
        and original_title
        and normalize_for_match(title) != normalize_for_match(original_title)
    ):
        return f"{title} ({original_title})"
    return title or original_title


def genre_display_name(genre_info: dict[str, Any], fallback: str) -> str:
    return str(genre_info.get("name") or fallback).strip() or fallback


async def resolve_explicit_genre(
    service: Any, query: str, authorization: str | None
) -> dict[str, Any] | None:
    hint = extract_explicit_genre_hint(query)
    if not hint:
        return None
    genres = await service._catalog_search_genres(hint, authorization)
    if not genres:
        return None
    best = (
        pick_best_candidate(
            hint,
            genres,
            lambda item: " ".join(
                [item.get("name", ""), " ".join(item.get("aliases") or [])]
            ),
        )
        or genres[0]
    )
    return best


def pick_single_recommendation(
    session: dict[str, Any], items: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    history_key = f"{key}_history"
    seen = [str(item) for item in session.get(history_key, []) if str(item)]
    unseen = [item for item in items if str(item.get("uuid")) not in seen]
    pool = unseen or items
    if not pool:
        return {}
    choice = random.choice(pool)
    chosen_id = str(choice.get("uuid") or "")
    if unseen:
        seen.append(chosen_id)
    else:
        seen = [chosen_id]
    session[history_key] = seen[-20:]
    return choice


async def resolve_person(
    service: Any,
    person_name: str,
    search_queries: list[str],
    authorization: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    collected: list[dict[str, Any]] = []
    used_query: str | None = None
    for candidate in candidate_queries(person_name, search_queries):
        people = await service._catalog_search_persons(candidate, authorization)
        if people:
            collected = people
            used_query = candidate
            break
    if not collected:
        token_candidates = [
            token
            for token in normalize_for_match(person_name).split()
            if len(token) >= 4
        ]
        for token in token_candidates:
            people = await service._catalog_search_persons(token, authorization)
            if people:
                collected = people
                used_query = token
                break
    if not collected:
        return None, [], used_query
    best = (
        pick_best_candidate(
            person_name, collected, lambda item: item.get("full_name", "")
        )
        or collected[0]
    )
    return best, person_alternatives(collected), used_query


async def resolve_film(
    service: Any,
    film_title: str,
    search_queries: list[str],
    authorization: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    collected: list[dict[str, Any]] = []
    used_query: str | None = None
    for candidate in candidate_queries(film_title, search_queries):
        films = await service._catalog_search_films(candidate, authorization)
        if films:
            collected = films
            used_query = candidate
            break
    if not collected:
        fallback = await service._catalog_list_top_films(authorization, limit=50)
        if fallback:
            collected = fallback
            used_query = "__top_films_fallback__"
    if not collected:
        return None, [], used_query
    best = (
        pick_best_candidate(
            film_title,
            collected,
            lambda item: " ".join(
                [
                    item.get("title", ""),
                    item.get("original_title", ""),
                    " ".join(item.get("title_aliases") or []),
                ]
            ),
        )
        or collected[0]
    )
    return best, film_alternatives(collected), used_query


async def load_film_details(
    service: Any, film_ids: Iterable[str], authorization: str | None
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for film_id in film_ids:
        try:
            details.append(await service._catalog_film_details(film_id, authorization))
        except httpx.HTTPStatusError:
            continue
    return details


async def resolve_genre_names(
    service: Any, genre_ids: Iterable[str], authorization: str | None
) -> list[str]:
    names: list[str] = []
    for genre_id in genre_ids:
        try:
            genre = await service._catalog_genre_details(genre_id, authorization)
            if genre.get("name"):
                names.append(genre["name"])
        except httpx.HTTPStatusError:
            names.append(genre_id)
    return names


def remember(session: dict[str, Any], context: dict[str, Any]) -> None:
    session.update({key: value for key, value in context.items() if value is not None})


def film_alternatives(films: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("uuid"),
            "title": item.get("title"),
            "rating": item.get("imdb_rating"),
        }
        for item in films[:3]
    ]


def person_alternatives(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("uuid"),
            "name": item.get("full_name"),
        }
        for item in people[:3]
    ]


def help_text() -> str:
    capabilities = get_capabilities().get("intents", [])
    visible = [item for item in capabilities if item["name"] != "help"]
    pieces = ", ".join(item["description"].lower() for item in visible[:6])
    return f"Я умею: {pieces}. Ещё могу показать ваши закладки и дать рекомендации после входа."
