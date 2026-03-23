from __future__ import annotations

from collections import Counter
from typing import Any

from core.settings import settings
from services.entity_resolver import (
    display_title,
    format_person_names_for_answer,
    genre_display_name,
    load_film_details,
    pick_single_recommendation,
    remember,
    resolve_explicit_genre,
    resolve_film,
    resolve_genre_names,
    resolve_person,
)
from services.query_parser import (
    candidate_queries,
    extract_film_title_with_context,
    extract_person_name_with_context,
)


async def handle_film_query(
    service: Any,
    intent: str,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
    film_title: str | None = None,
    search_queries: list[str] | None = None,
):
    title = film_title or extract_film_title_with_context(query, session)
    if not title:
        return service._response(
            query=query,
            session_id=session_id,
            intent=intent,
            answer_text="Не удалось понять название фильма. Лучше написать его в кавычках или сначала выбрать фильм поиском.",
            confidence=0.2,
            used_services=[],
            metadata={},
            context=session,
        )

    film, alternatives, used_query = await resolve_film(
        service, title, search_queries or [], authorization
    )
    if not film:
        return service._response(
            query=query,
            session_id=session_id,
            intent=intent,
            answer_text=f"Не нашёл фильм по запросу: {title}.",
            confidence=0.2,
            used_services=["catalog"],
            metadata={
                "film_query": title,
                "search_queries": candidate_queries(title, search_queries or []),
            },
            context=session,
            alternatives=alternatives,
        )

    cache_key = service._public_response_cache_key(
        intent, entity_type="film", entity_id=str(film["uuid"])
    )
    if not service._has_bearer(authorization):
        cached = await service._load_cached_public_response(
            cache_key, query, session_id, session
        )
        if cached is not None:
            return cached

    detail = await service._catalog_film_details(film["uuid"], authorization)
    genre_names = await resolve_genre_names(
        service, detail.get("genre") or [], authorization
    )
    matched_title = display_title(detail or film) or detail.get(
        "title", film.get("title", title)
    )

    result = {
        "type": "film",
        "id": detail.get("uuid", film.get("uuid")),
        "title": matched_title,
        "rating": detail.get("imdb_rating"),
        "duration": detail.get("runtime_minutes"),
        "genres": genre_names,
        "director": ", ".join(detail.get("directors") or []),
        "description": detail.get("description"),
    }
    context = {
        "film_id": result["id"],
        "film_title": matched_title,
        "person_name": result["director"],
    }
    remember(session, context)

    if intent == "film_rating":
        rating = detail.get("imdb_rating")
        answer = (
            f"Рейтинг фильма «{matched_title}» — {rating}."
            if rating is not None
            else f"У фильма «{matched_title}» пока нет рейтинга IMDb."
        )
    elif intent == "film_director":
        directors = detail.get("directors") or []
        formatted_directors = (
            await format_person_names_for_answer(service, directors, authorization)
            if directors
            else []
        )
        result["director"] = ", ".join(formatted_directors)
        context["person_name"] = result["director"]
        answer = (
            f'Режиссёр фильма «{matched_title}» — {", ".join(formatted_directors)}.'
            if formatted_directors
            else f"У меня нет данных о режиссёре фильма «{matched_title}»."
        )
    elif intent == "film_duration":
        runtime = detail.get("runtime_minutes")
        answer = (
            f"Фильм «{matched_title}» длится {runtime} минут."
            if runtime
            else f"У меня нет данных о длительности фильма «{matched_title}»."
        )
    elif intent == "film_genres":
        answer = (
            f'У фильма «{matched_title}» жанры: {", ".join(genre_names)}.'
            if genre_names
            else f"У меня нет данных о жанрах фильма «{matched_title}»."
        )
    else:
        description = str(detail.get("description") or "").strip()
        extra_parts: list[str] = []
        if detail.get("imdb_rating") is not None:
            extra_parts.append(f'рейтинг IMDb {detail["imdb_rating"]}')
        if detail.get("runtime_minutes"):
            extra_parts.append(f'длительность {detail["runtime_minutes"]} минут')
        if genre_names:
            extra_parts.append(f'жанры: {", ".join(genre_names)}')
        extra = f" Также: {'; '.join(extra_parts)}." if extra_parts else ""
        if description:
            answer = (
                f"Краткая сводка по фильму «{matched_title}»: {description}.{extra}"
            )
        else:
            parts = [f"«{matched_title}»"]
            if detail.get("imdb_rating") is not None:
                parts.append(f'рейтинг IMDb {detail["imdb_rating"]}')
            if detail.get("runtime_minutes"):
                parts.append(f'длительность {detail["runtime_minutes"]} минут')
            if genre_names:
                parts.append(f'жанры: {", ".join(genre_names)}')
            answer = "Фильм " + ", ".join(parts) + "."

    return service._response(
        query=query,
        session_id=session_id,
        intent=intent,
        answer_text=answer,
        confidence=0.92,
        used_services=["catalog"],
        metadata={
            "film_id": result["id"],
            "matched_title": matched_title,
            "search_query": used_query,
            "public_response_cache_key": cache_key,
        },
        context=session,
        result=result,
        alternatives=alternatives,
    )


async def handle_person_movie_count(
    service: Any,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
    person_name: str | None = None,
    search_queries: list[str] | None = None,
):
    raw_name = person_name or extract_person_name_with_context(query, session)
    if not raw_name:
        return service._response(
            query=query,
            session_id=session_id,
            intent="person_movie_count",
            answer_text="Не удалось понять имя автора. Лучше написать его в кавычках.",
            confidence=0.2,
            used_services=[],
            metadata={},
            context=session,
        )
    person, alternatives, used_query = await resolve_person(
        service, raw_name, search_queries or [], authorization
    )
    if not person:
        return service._response(
            query=query,
            session_id=session_id,
            intent="person_movie_count",
            answer_text=f"Не нашёл человека по запросу: {raw_name}.",
            confidence=0.2,
            used_services=["catalog"],
            metadata={
                "person_query": raw_name,
                "search_queries": candidate_queries(raw_name, search_queries or []),
            },
            context=session,
            alternatives=alternatives,
        )
    cache_key = service._public_response_cache_key(
        "person_movie_count", entity_type="person", entity_id=str(person["uuid"])
    )
    if not service._has_bearer(authorization):
        cached = await service._load_cached_public_response(
            cache_key, query, session_id, session
        )
        if cached is not None:
            return cached

    detail = await service._catalog_person_details(person["uuid"], authorization)
    films = detail.get("films") or []
    matched_name = detail.get("full_name", raw_name)
    remember(
        session,
        {
            "person_id": detail.get("uuid", person.get("uuid")),
            "person_name": matched_name,
        },
    )
    answer = f"У {matched_name} — {len(films)} фильм(ов) в каталоге."
    return service._response(
        query=query,
        session_id=session_id,
        intent="person_movie_count",
        answer_text=answer,
        confidence=0.9,
        used_services=["catalog"],
        metadata={
            "person_id": detail.get("uuid", person.get("uuid")),
            "matched_name": matched_name,
            "search_query": used_query,
            "public_response_cache_key": cache_key,
        },
        context=session,
        result={
            "type": "person",
            "name": matched_name,
            "count": len(films),
            "films": films,
        },
        alternatives=alternatives,
    )


async def handle_person_filmography(
    service: Any,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
    person_name: str | None = None,
    search_queries: list[str] | None = None,
):
    raw_name = person_name or extract_person_name_with_context(query, session)
    if not raw_name:
        return service._response(
            query=query,
            session_id=session_id,
            intent="person_filmography",
            answer_text="Не удалось понять имя человека. Лучше написать его в кавычках.",
            confidence=0.2,
            used_services=[],
            metadata={},
            context=session,
        )
    person, alternatives, used_query = await resolve_person(
        service, raw_name, search_queries or [], authorization
    )
    if not person:
        return service._response(
            query=query,
            session_id=session_id,
            intent="person_filmography",
            answer_text=f"Не нашёл человека по запросу: {raw_name}.",
            confidence=0.2,
            used_services=["catalog"],
            metadata={
                "person_query": raw_name,
                "search_queries": candidate_queries(raw_name, search_queries or []),
            },
            context=session,
            alternatives=alternatives,
        )
    cache_key = service._public_response_cache_key(
        "person_filmography", entity_type="person", entity_id=str(person["uuid"])
    )
    if not service._has_bearer(authorization):
        cached = await service._load_cached_public_response(
            cache_key, query, session_id, session
        )
        if cached is not None:
            return cached

    detail = await service._catalog_person_details(person["uuid"], authorization)
    films = detail.get("films") or []
    matched_name = detail.get("full_name", raw_name)
    remember(
        session,
        {
            "person_id": detail.get("uuid", person.get("uuid")),
            "person_name": matched_name,
        },
    )
    if not films:
        answer = f"У меня нет фильмографии для {matched_name}."
    else:
        film_details = await load_film_details(
            service,
            [item.get("uuid") for item in films if item.get("uuid")],
            authorization,
        )
        details_by_id = {
            item.get("uuid"): item for item in film_details if item.get("uuid")
        }
        titles = ", ".join(
            display_title(details_by_id.get(item.get("uuid")) or item)
            for item in films[:5]
            if display_title(details_by_id.get(item.get("uuid")) or item)
        )
        answer = f"У {matched_name} есть такие фильмы: {titles}."
    return service._response(
        query=query,
        session_id=session_id,
        intent="person_filmography",
        answer_text=answer,
        confidence=0.88,
        used_services=["catalog"],
        metadata={
            "person_id": detail.get("uuid", person.get("uuid")),
            "matched_name": matched_name,
            "search_query": used_query,
            "public_response_cache_key": cache_key,
        },
        context=session,
        result={"type": "person", "name": matched_name, "films": films},
        alternatives=alternatives,
    )


async def handle_bookmarks(
    service: Any,
    query: str,
    authorization: str,
    session_id: str,
    session: dict[str, Any],
):
    me = await service._me_or_none(authorization)
    if me is None:
        return service._auth_required_response(query, session_id, session, "bookmarks")
    bookmarks = await service.ugc_client.bookmarks_by_user(str(me["id"]), authorization)
    if not bookmarks:
        return service._response(
            query=query,
            session_id=session_id,
            intent="bookmarks",
            answer_text="У вас пока нет закладок.",
            confidence=0.95,
            used_services=["auth", "ugc"],
            metadata={"bookmark_count": 0},
            context=session,
            result={"type": "bookmarks", "items": []},
        )
    details = await load_film_details(
        service, [item["film_id"] for item in bookmarks], authorization
    )
    titles = ", ".join(
        display_title(detail) for detail in details[:5] if display_title(detail)
    )
    answer = f"У вас в закладках {len(bookmarks)} фильм(ов): {titles}."
    return service._response(
        query=query,
        session_id=session_id,
        intent="bookmarks",
        answer_text=answer,
        confidence=0.95,
        used_services=["auth", "ugc", "catalog"],
        metadata={"bookmark_count": len(bookmarks)},
        context=session,
        result={"type": "bookmarks", "items": details},
    )


async def handle_public_recommend_by_genre(
    service: Any,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
    genre_info: dict[str, Any],
):
    genre_id = str(genre_info.get("id") or genre_info.get("uuid") or "")
    genre_label = genre_display_name(genre_info, genre_id or "этот жанр")
    if not genre_id:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_general",
            answer_text="Не удалось определить жанр. Попробуйте назвать его чуть точнее.",
            confidence=0.45,
            used_services=["catalog"],
            metadata={},
            context=session,
            result={"type": "recommendations", "items": []},
        )
    candidates = await service._catalog_films_by_genre(genre_id, authorization)
    if not candidates:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_general",
            answer_text=f"Пока не нашёл фильмов в жанре {genre_label}.",
            confidence=0.65,
            used_services=["catalog"],
            metadata={"genre": genre_label},
            context=session,
            result={"type": "recommendations", "genre": genre_label, "items": []},
        )
    ranked = sorted(
        candidates, key=lambda item: item.get("imdb_rating") or 0, reverse=True
    )[:10]
    choice = pick_single_recommendation(session, ranked, f"genre:{genre_id}")
    display = display_title(choice)
    remember(session, {"film_id": choice.get("uuid"), "film_title": display})
    return service._response(
        query=query,
        session_id=session_id,
        intent="recommend_general",
        answer_text=f'Из жанра {genre_label} попробуйте фильм «{display}». Рейтинг IMDb — {choice.get("imdb_rating", "—")}. Нажмите «Ещё», если нужен другой вариант.',
        confidence=0.87,
        used_services=["catalog"],
        metadata={"genre": genre_label, "can_repeat": True},
        context=session,
        result={
            "type": "recommendations",
            "genre": genre_label,
            "item": choice,
            "items": [choice],
            "can_repeat": True,
        },
    )


async def handle_recommend_by_genre(
    service: Any,
    query: str,
    authorization: str,
    session_id: str,
    session: dict[str, Any],
):
    me = await service._me_or_none(authorization)
    if me is None:
        return service._auth_required_response(
            query, session_id, session, "recommend_by_genre"
        )
    bookmarks = await service.ugc_client.bookmarks_by_user(str(me["id"]), authorization)
    likes = await service.ugc_client.likes_by_user(str(me["id"]), authorization)
    positive_likes = [item for item in likes if int(item.get("value", 0)) >= 7]
    interacted_ids = list({item["film_id"] for item in [*bookmarks, *positive_likes]})
    if not interacted_ids:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_by_genre",
            answer_text="Пока не на что опереться. Добавьте хотя бы один фильм в закладки или поставьте высокую оценку.",
            confidence=0.8,
            used_services=["auth", "ugc"],
            metadata={"interactions": 0},
            context=session,
            result={"type": "recommendations", "items": []},
        )

    details = await load_film_details(service, interacted_ids, authorization)
    genre_ids = [
        genre_id for detail in details for genre_id in (detail.get("genre") or [])
    ]
    if not genre_ids:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_by_genre",
            answer_text="Я не смог определить ваши любимые жанры по текущим действиям.",
            confidence=0.6,
            used_services=["auth", "ugc", "catalog"],
            metadata={},
            context=session,
            result={"type": "recommendations", "items": []},
        )

    favorite_genre_id, _ = Counter(genre_ids).most_common(1)[0]
    genre_info = await service._catalog_genre_details(favorite_genre_id, authorization)
    genre_name = genre_display_name(genre_info, favorite_genre_id)
    candidates = await service._catalog_films_by_genre(favorite_genre_id, authorization)
    recommended = [
        item for item in candidates if item.get("uuid") not in set(interacted_ids)
    ]
    recommended = recommended[: settings.RECOMMENDATION_LIMIT]
    if not recommended:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_by_genre",
            answer_text=f"Ваш любимый жанр — {genre_name}, но новых рекомендаций по нему у меня пока нет.",
            confidence=0.78,
            used_services=["auth", "ugc", "catalog"],
            metadata={"favorite_genre": genre_name},
            context=session,
            result={"type": "recommendations", "genre": genre_name, "items": []},
        )
    items = ", ".join(
        f"{display_title(item)} ({item.get('imdb_rating', 'n/a')})"
        for item in recommended
    )
    answer = f"Похоже, вам нравится жанр {genre_name}. Могу предложить: {items}."
    return service._response(
        query=query,
        session_id=session_id,
        intent="recommend_by_genre",
        answer_text=answer,
        confidence=0.9,
        used_services=["auth", "ugc", "catalog"],
        metadata={
            "favorite_genre": genre_name,
            "recommendation_count": len(recommended),
        },
        context=session,
        result={"type": "recommendations", "genre": genre_name, "items": recommended},
    )


async def handle_recommend_general(
    service: Any,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
):
    explicit_genre = await resolve_explicit_genre(service, query, authorization)
    if explicit_genre is not None:
        return await handle_public_recommend_by_genre(
            service, query, authorization, session_id, session, explicit_genre
        )

    top_films = await service._catalog_list_top_films(
        authorization, limit=max(settings.RECOMMENDATION_LIMIT, 10)
    )
    if not top_films:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_general",
            answer_text="Пока не могу предложить фильм: каталог пуст.",
            confidence=0.6,
            used_services=["catalog"],
            metadata={},
            context=session,
            result={"type": "recommendations", "items": []},
        )
    top_candidates = sorted(
        top_films, key=lambda item: item.get("imdb_rating") or 0, reverse=True
    )[:10]
    choice = pick_single_recommendation(
        session, top_candidates, "general_recommendations"
    )
    display = display_title(choice)
    remember(session, {"film_id": choice.get("uuid"), "film_title": display})
    return service._response(
        query=query,
        session_id=session_id,
        intent="recommend_general",
        answer_text=f'Попробуйте фильм «{display}». Рейтинг IMDb — {choice.get("imdb_rating", "—")}. Нажмите «Ещё», если нужен другой вариант.',
        confidence=0.88,
        used_services=["catalog"],
        metadata={"can_repeat": True},
        context=session,
        result={
            "type": "recommendations",
            "item": choice,
            "items": [choice],
            "can_repeat": True,
        },
    )


async def handle_recommend_by_person(
    service: Any,
    query: str,
    authorization: str | None,
    session_id: str,
    session: dict[str, Any],
    person_name: str | None = None,
    search_queries: list[str] | None = None,
):
    raw_name = person_name or extract_person_name_with_context(query, session)
    if not raw_name:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_by_person",
            answer_text="Не удалось понять, про какого человека идёт речь. Лучше написать имя в кавычках.",
            confidence=0.2,
            used_services=[],
            metadata={},
            context=session,
        )
    person, alternatives, used_query = await resolve_person(
        service, raw_name, search_queries or [], authorization
    )
    if not person:
        return service._response(
            query=query,
            session_id=session_id,
            intent="recommend_by_person",
            answer_text=f"Не нашёл человека по запросу: {raw_name}.",
            confidence=0.2,
            used_services=["catalog"],
            metadata={
                "person_query": raw_name,
                "search_queries": candidate_queries(raw_name, search_queries or []),
            },
            context=session,
            alternatives=alternatives,
        )
    detail = await service._catalog_person_details(person["uuid"], authorization)
    films = detail.get("films") or []
    matched_name = detail.get("full_name", raw_name)
    remember(
        session,
        {
            "person_id": detail.get("uuid", person.get("uuid")),
            "person_name": matched_name,
        },
    )
    if not films:
        answer = f"У меня пока нет фильмов, чтобы рекомендовать по {matched_name}."
        items: list[dict[str, Any]] = []
    else:
        sorted_films = sorted(
            films, key=lambda item: item.get("imdb_rating") or 0, reverse=True
        )
        items = sorted_films[: settings.RECOMMENDATION_LIMIT]
        answer = (
            f"Могу предложить фильмы с участием или от {matched_name}: "
            + ", ".join(
                f"{display_title(item)} ({item.get('imdb_rating', 'n/a')})"
                for item in items
            )
            + "."
        )
    return service._response(
        query=query,
        session_id=session_id,
        intent="recommend_by_person",
        answer_text=answer,
        confidence=0.86,
        used_services=["catalog"],
        metadata={
            "person_id": detail.get("uuid", person.get("uuid")),
            "matched_name": matched_name,
            "search_query": used_query,
        },
        context=session,
        result={"type": "recommendations", "items": items, "person_name": matched_name},
        alternatives=alternatives,
    )
