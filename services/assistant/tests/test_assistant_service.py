from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, status

from domain.llm_models import LlmParseResult
from domain.models import AssistantFeedbackRequest
from services.assistant import AssistantService
from services.session_store import (
    InMemoryFeedbackStore,
    InMemoryJsonCacheStore,
    InMemoryLlmCircuitStore,
)


class FakeSessionStore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}
        self.saved_snapshots: list[tuple[str, dict[str, Any]]] = []

    async def load(self, session_id: str) -> dict[str, Any]:
        return dict(self.data.get(session_id, {}))

    async def save(self, session_id: str, session: dict[str, Any]) -> None:
        snapshot = dict(session)
        self.data[session_id] = snapshot
        self.saved_snapshots.append((session_id, snapshot))


class FakeAuthClient:
    def __init__(self, user: dict[str, Any] | None = None):
        self.user = user
        self.service_auth_calls = 0

    async def me(self, authorization: str | None) -> dict[str, Any]:
        if not authorization or self.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return self.user

    async def service_authorization(self, force_refresh: bool = False) -> str:
        self.service_auth_calls += 1
        return "Bearer service-token"


class FakeCatalogClient:
    def __init__(self):
        self.film_details_calls = 0
        self.person_details_calls = 0
        self.top_films = [
            {
                "uuid": "film-1",
                "title": "Тихая Луна",
                "original_title": "Silent Moon",
                "title_aliases": ["Silent Moon", "Сайлент мун"],
                "imdb_rating": 8.1,
            },
            {
                "uuid": "film-2",
                "title": "Лунар: Серебряная звезда",
                "original_title": "Lunar: The Silver Star",
                "title_aliases": ["Lunar: The Silver Star"],
                "imdb_rating": 7.8,
            },
            {
                "uuid": "film-3",
                "title": "Красный маяк",
                "original_title": "Red Lighthouse",
                "title_aliases": ["Red Lighthouse"],
                "imdb_rating": 7.5,
            },
            {
                "uuid": "film-6",
                "title": "Молодёжка",
                "original_title": "Young Hearts Arena",
                "title_aliases": ["Young Hearts Arena", "Молодежка"],
                "imdb_rating": 7.4,
            },
        ]
        self.film_details_map = {
            "film-1": {
                "uuid": "film-1",
                "title": "Тихая Луна",
                "original_title": "Silent Moon",
                "title_aliases": ["Silent Moon", "Сайлент мун"],
                "imdb_rating": 8.1,
                "runtime_minutes": 103,
                "genre": ["genre-sci-fi"],
                "directors": ["Луна Сильвер"],
                "description": "Тихая фантастическая драма.",
            },
            "film-2": {
                "uuid": "film-2",
                "title": "Лунар: Серебряная звезда",
                "original_title": "Lunar: The Silver Star",
                "title_aliases": ["Lunar: The Silver Star"],
                "imdb_rating": 7.8,
                "runtime_minutes": 111,
                "genre": ["genre-drama"],
                "directors": ["Алекс Дрэгонмастер"],
                "description": "Классическое приключение.",
            },
            "film-3": {
                "uuid": "film-3",
                "title": "Красный маяк",
                "original_title": "Red Lighthouse",
                "title_aliases": ["Red Lighthouse"],
                "imdb_rating": 7.5,
                "runtime_minutes": 95,
                "genre": ["genre-drama"],
                "directors": ["Нора Вейл"],
                "description": "Детектив у моря.",
            },
            "film-6": {
                "uuid": "film-6",
                "title": "Молодёжка",
                "original_title": "Young Hearts Arena",
                "title_aliases": ["Young Hearts Arena", "Молодежка"],
                "imdb_rating": 7.4,
                "runtime_minutes": 101,
                "genre": ["genre-drama"],
                "directors": ["Артём Белов"],
                "description": "Спортивная драма.",
            },
            "film-7": {
                "uuid": "film-7",
                "title": "Тайна без рейтинга",
                "original_title": "Zero Rating Mystery",
                "title_aliases": ["Zero Rating Mystery"],
                "imdb_rating": None,
                "runtime_minutes": 112,
                "genre": ["genre-thriller"],
                "directors": ["Нора Вейл"],
                "description": "Детектив без рейтинга.",
            },
            "film-8": {
                "uuid": "film-8",
                "title": "Ночной курьер",
                "original_title": "Night Courier",
                "title_aliases": ["Night Courier"],
                "imdb_rating": 7.8,
                "runtime_minutes": 101,
                "genre": ["genre-thriller"],
                "directors": ["Игорь Север"],
                "description": "Ночная доставка чужих тайн.",
            },
            "film-9": {
                "uuid": "film-9",
                "title": "Северный ветер",
                "original_title": "North Wind",
                "title_aliases": ["North Wind"],
                "imdb_rating": 7.1,
                "runtime_minutes": 104,
                "genre": ["genre-drama"],
                "directors": ["Игорь Север"],
                "description": "Дорога, снег и выбор.",
            },
            "film-10": {
                "uuid": "film-10",
                "title": "Полуночный маршрут",
                "original_title": "Midnight Route",
                "title_aliases": ["Midnight Route"],
                "imdb_rating": 6.9,
                "runtime_minutes": 99,
                "genre": ["genre-thriller"],
                "directors": ["Игорь Север"],
                "description": "Напряжённая ночная поездка.",
            },
        }
        self.genre_names = {
            "genre-sci-fi": {
                "uuid": "genre-sci-fi",
                "name": "Фантастика",
                "aliases": ["Sci-Fi"],
            },
            "genre-drama": {
                "uuid": "genre-drama",
                "name": "Драма",
                "aliases": ["Drama"],
            },
            "genre-thriller": {
                "uuid": "genre-thriller",
                "name": "Детектив",
                "aliases": ["Mystery"],
            },
        }
        self.person_search_results = {
            "Луна Сильвер": [
                {
                    "uuid": "person-1",
                    "full_name": "Луна Сильвер",
                    "aliases": ["Luna Silver"],
                },
            ],
            "Игорь Север": [
                {
                    "uuid": "person-2",
                    "full_name": "Игорь Север",
                    "aliases": ["Igor Sever"],
                },
            ],
        }
        self.person_details_map = {
            "person-1": {
                "uuid": "person-1",
                "full_name": "Луна Сильвер",
                "films": [
                    {"uuid": "film-1", "title": "Тихая Луна", "roles": ["director"]},
                    {"uuid": "film-2", "title": "Лунар: Серебряная звезда", "roles": ["director"]},
                    {"uuid": "film-3", "title": "Красный маяк", "roles": ["writer"]},
                ],
            },
            "person-2": {
                "uuid": "person-2",
                "full_name": "Игорь Север",
                "films": [
                    {
                        "uuid": "film-7",
                        "title": "Тайна без рейтинга",
                        "imdb_rating": None,
                        "roles": ["actor"],
                    },
                    {
                        "uuid": "film-8",
                        "title": "Ночной курьер",
                        "imdb_rating": 7.8,
                        "roles": ["director"],
                    },
                    {
                        "uuid": "film-9",
                        "title": "Северный ветер",
                        "imdb_rating": 7.1,
                        "roles": ["director", "writer"],
                    },
                    {
                        "uuid": "film-10",
                        "title": "Полуночный маршрут",
                        "imdb_rating": 6.9,
                        "roles": ["director"],
                    },
                ],
            },
        }

    async def search_films(
        self, query: str, authorization: str
    ) -> list[dict[str, Any]]:
        query_lower = query.lower()
        return [
            film
            for film in self.top_films
            if query_lower in film["title"].lower()
            or query_lower in (film.get("original_title") or "").lower()
            or any(
                query_lower in alias.lower()
                for alias in (film.get("title_aliases") or [])
            )
        ]

    async def search_genres(
        self, query: str, authorization: str
    ) -> list[dict[str, Any]]:
        query_lower = query.lower()
        return [
            {"id": genre_id, **payload}
            for genre_id, payload in self.genre_names.items()
            if query_lower in payload["name"].lower()
            or any(query_lower in alias.lower() for alias in payload.get("aliases", []))
        ]

    async def list_top_films(
        self, authorization: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        return self.top_films[:limit]

    async def film_details(self, film_id: str, authorization: str) -> dict[str, Any]:
        self.film_details_calls += 1
        return self.film_details_map[film_id]

    async def genre_details(self, genre_id: str, authorization: str) -> dict[str, Any]:
        return self.genre_names[genre_id]

    async def films_by_genre(
        self, genre_id: str, authorization: str
    ) -> list[dict[str, Any]]:
        return [
            film
            for film in self.top_films
            if genre_id in self.film_details_map[film["uuid"]].get("genre", [])
        ]

    async def search_persons(
        self, query: str, authorization: str
    ) -> list[dict[str, Any]]:
        for key, value in self.person_search_results.items():
            if query.lower() in key.lower():
                return value
        return []

    async def person_details(
        self, person_id: str, authorization: str
    ) -> dict[str, Any]:
        self.person_details_calls += 1
        return self.person_details_map[person_id]


class FakeUgcClient:
    def __init__(self):
        self.bookmarks = [{"film_id": "film-3"}]
        self.likes = [{"film_id": "film-2", "value": 9}]

    async def bookmarks_by_user(
        self, user_id: str, authorization: str
    ) -> list[dict[str, Any]]:
        return list(self.bookmarks)

    async def likes_by_user(
        self, user_id: str, authorization: str
    ) -> list[dict[str, Any]]:
        return list(self.likes)


class FakeLlmClient:
    def __init__(self, result: LlmParseResult | None):
        self.result = result
        self.calls = 0

    @staticmethod
    def is_enabled() -> bool:
        return True

    async def parse_query(
        self, query: str, session_context: dict[str, Any]
    ) -> LlmParseResult | None:
        self.calls += 1
        return self.result


class FakeFailingLlmClient:
    def __init__(self):
        self.calls = 0

    @staticmethod
    def is_enabled() -> bool:
        return True

    async def parse_query(
        self, query: str, session_context: dict[str, Any]
    ) -> LlmParseResult | None:
        self.calls += 1
        return None


def build_service(
    user: dict[str, Any] | None = None,
    *,
    session_store: FakeSessionStore | None = None,
    llm_client: Any | None = None,
    parse_cache: InMemoryJsonCacheStore | None = None,
    response_cache: InMemoryJsonCacheStore | None = None,
    feedback_store: InMemoryFeedbackStore | None = None,
    llm_circuit_store: InMemoryLlmCircuitStore | None = None,
) -> tuple[
    AssistantService, FakeAuthClient, FakeCatalogClient, FakeUgcClient, FakeSessionStore
]:
    auth_client = FakeAuthClient(user=user)
    catalog_client = FakeCatalogClient()
    ugc_client = FakeUgcClient()
    shared_store = session_store or FakeSessionStore()
    service = AssistantService(
        auth_client=auth_client,
        catalog_client=catalog_client,
        ugc_client=ugc_client,
        session_store=shared_store,
        llm_client=llm_client,
        parse_cache=parse_cache or InMemoryJsonCacheStore(),
        public_response_cache=response_cache or InMemoryJsonCacheStore(),
        feedback_store=feedback_store or InMemoryFeedbackStore(),
        llm_circuit_store=llm_circuit_store
        or InMemoryLlmCircuitStore(failure_threshold=1, cooldown_seconds=60),
    )
    return service, auth_client, catalog_client, ugc_client, shared_store


def test_recommend_general_returns_structured_recommendations_and_uses_service_token() -> (
    None
):
    service, auth_client, _, _, store = build_service()

    response = asyncio.run(
        service.handle_query("посоветуй фильм", authorization=None, session_id="sess-1")
    )

    assert response.intent == "recommend_general"
    assert response.result["type"] == "recommendations"
    assert len(response.result["items"]) == 1
    assert response.result["item"]["uuid"] == response.result["items"][0]["uuid"]
    assert response.result["can_repeat"] is True
    assert response.context["film_title"]
    assert auth_client.service_auth_calls == 1
    assert store.data["sess-1"]["film_title"] == response.context["film_title"]


def test_bookmarks_without_auth_requires_login() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "что у меня в закладках?", authorization=None, session_id="sess-2"
        )
    )

    assert response.intent == "bookmarks"
    assert response.requires_auth is True
    assert "войти в систему" in response.answer_text


def test_recommend_by_genre_skips_already_interacted_films() -> None:
    service, _, _, _, _ = build_service(user={"id": "user-1"})

    response = asyncio.run(
        service.handle_query(
            "посоветуй мне фильмы по моим любимым жанрам",
            authorization="Bearer user-token",
            session_id="sess-3",
        )
    )

    assert response.intent == "recommend_by_genre"
    assert response.result["genre"].startswith("Драма")
    titles = [item["title"] for item in response.result["items"]]
    assert "Тихая Луна" not in titles
    assert "Лунар: Серебряная звезда" not in titles
    assert titles == ["Молодёжка"]
    assert "Драма" in response.answer_text


def test_film_followup_uses_shared_session_store_across_service_instances() -> None:
    shared_store = FakeSessionStore()
    service_first, _, _, _, _ = build_service(session_store=shared_store)
    service_second, _, _, _, _ = build_service(session_store=shared_store)

    asyncio.run(
        service_first.handle_query(
            "посоветуй фильм", authorization=None, session_id="sess-4"
        )
    )
    response = asyncio.run(
        service_second.handle_query(
            "кто режиссёр этого фильма?", authorization=None, session_id="sess-4"
        )
    )

    assert response.intent == "film_director"
    assert response.result["director"]
    assert response.result["title"] == response.context["film_title"]


def test_person_followup_uses_shared_session_store_across_service_instances() -> None:
    shared_store = FakeSessionStore()
    service_first, _, _, _, _ = build_service(session_store=shared_store)
    service_second, _, _, _, _ = build_service(session_store=shared_store)

    asyncio.run(
        service_first.handle_query(
            'какие фильмы у "Луна Сильвер"?', authorization=None, session_id="sess-5"
        )
    )
    response = asyncio.run(
        service_second.handle_query(
            "сколько фильмов у неё?", authorization=None, session_id="sess-5"
        )
    )

    assert response.intent == "person_movie_count"
    assert "Луна Сильвер" in response.answer_text
    assert response.result["count"] == 3


def test_detects_director_intent_for_kto_snyal() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "Кто снял фильм Сайлент мун?", authorization=None, session_id="sess-6"
        )
    )

    assert response.intent == "film_director"
    assert "Режиссёр фильма" in response.answer_text
    assert "Тихая Луна" in response.answer_text


def test_public_search_enriches_cards() -> None:
    service, _, _, _, _ = build_service()

    items = asyncio.run(service.public_search("тихая луна", None))

    assert items
    first = items[0]
    assert first["title"] == "Тихая Луна"
    assert first["directors"] == ["Луна Сильвер"]
    assert "Фантастика" in first["genre"]


def test_director_answer_uses_russian_person_name_in_response() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            'кто режиссёр фильма "Тихая Луна"?', authorization=None, session_id="sess-7"
        )
    )

    assert response.intent == "film_director"
    assert "Луна Сильвер" in response.answer_text
    assert response.result["director"] == "Луна Сильвер"


def test_detects_overview_intent_for_summary_phrases() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "дай короткую сводку по фильму Тихая Луна",
            authorization=None,
            session_id="sess-8",
        )
    )

    assert response.intent == "film_overview"
    assert response.result["type"] == "film"
    assert response.result["description"]
    assert "Краткая сводка" in response.answer_text


def test_llm_parse_result_is_cached_for_low_confidence_queries() -> None:
    llm_client = FakeLlmClient(
        LlmParseResult(
            intent="film_overview",
            confidence=0.91,
            film_title="Тихая Луна",
            person_name=None,
            search_queries=["Тихая Луна"],
            requires_auth=False,
            reason="matched by llm",
        )
    )
    parse_cache = InMemoryJsonCacheStore()
    service, _, _, _, _ = build_service(llm_client=llm_client, parse_cache=parse_cache)

    first = asyncio.run(
        service.handle_query("объясни что там за кино тихая луна", None, "sess-9")
    )
    second = asyncio.run(
        service.handle_query("объясни что там за кино тихая луна", None, "sess-10")
    )

    assert first.intent == "film_overview"
    assert second.intent == "film_overview"
    assert llm_client.calls == 1
    assert second.metadata["plan_source"] == "parse_cache"
    assert parse_cache.data


def test_public_film_response_is_cached_by_canonical_entity() -> None:
    response_cache = InMemoryJsonCacheStore()
    service, _, catalog_client, _, _ = build_service(response_cache=response_cache)

    first = asyncio.run(
        service.handle_query("кто режиссёр фильма Тихая Луна?", None, "sess-11")
    )
    second = asyncio.run(service.handle_query("кто снял Silent Moon?", None, "sess-12"))

    assert first.intent == "film_director"
    assert second.intent == "film_director"
    assert catalog_client.film_details_calls == 1
    assert second.metadata["response_cache_hit"] is True


def test_llm_circuit_breaker_opens_after_failure_and_skips_extra_llm_calls() -> None:
    llm_client = FakeFailingLlmClient()
    circuit = InMemoryLlmCircuitStore(failure_threshold=1, cooldown_seconds=60)
    service, _, _, _, _ = build_service(
        llm_client=llm_client, llm_circuit_store=circuit
    )

    first = asyncio.run(
        service.handle_query("что-то очень странное и непонятное", None, "sess-13")
    )
    second = asyncio.run(
        service.handle_query("что-то очень странное и непонятное", None, "sess-14")
    )

    assert first.intent == "help"
    assert second.intent == "help"
    assert llm_client.calls == 1
    assert second.metadata["plan_source"] == "llm_circuit_open"


def test_feedback_is_recorded_for_offline_learning() -> None:
    feedback_store = InMemoryFeedbackStore()
    service, _, _, _, _ = build_service(feedback_store=feedback_store)

    response = asyncio.run(
        service.submit_feedback(
            AssistantFeedbackRequest(
                session_id="sess-15",
                query="кто снял тихую луну",
                reaction="up",
                intent="film_director",
                metadata={"parse_cache_key": "v1|kto snyal tihuyu lunu"},
            )
        )
    )

    assert response.status == "ok"
    assert feedback_store.events
    assert feedback_store.events[0]["reaction"] == "up"
    assert feedback_store.events[0]["intent"] == "film_director"


def test_detects_filmography_for_kakie_filmy_snyal_without_llm() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "какие фильмы снял Игорь Север?",
            authorization=None,
            session_id="sess-16",
        )
    )

    assert response.intent == "person_filmography"
    assert response.metadata["plan_source"] == "deterministic"
    assert "Фильмы режиссёра Игорь Север" in response.answer_text
    assert "Ночной курьер" in response.answer_text
    assert "Северный ветер" in response.answer_text
    assert "Полуночный маршрут" in response.answer_text
    assert "Тайна без рейтинга" not in response.answer_text


def test_followup_overview_uses_session_for_o_chem_etot_film() -> None:
    shared_store = FakeSessionStore()
    service, _, _, _, _ = build_service(session_store=shared_store)

    asyncio.run(
        service.handle_query(
            "кто режиссёр фильма Тихая Луна?",
            authorization=None,
            session_id="sess-17",
        )
    )
    response = asyncio.run(
        service.handle_query(
            "о чем этот фильм?",
            authorization=None,
            session_id="sess-17",
        )
    )

    assert response.intent == "film_overview"
    assert response.metadata["plan_source"] == "deterministic"
    assert response.result["title"] == "Тихая Луна (Silent Moon)"
    assert "Краткая сводка" in response.answer_text


def test_recommend_by_person_uses_film_details_and_omits_rating_labels_in_text() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            'посоветуй фильмы режиссёра "Луна Сильвер"',
            authorization=None,
            session_id="sess-18",
        )
    )

    assert response.intent == "recommend_by_person"
    assert "Тихая Луна" in response.answer_text
    assert "Лунар: Серебряная звезда" in response.answer_text
    assert "без рейтинга IMDb" not in response.answer_text
    assert "n/a" not in response.answer_text.lower()
    assert response.result["items"][0]["imdb_rating"] == 8.1
    assert response.result["items"][1]["imdb_rating"] == 7.8


def test_detects_feminine_person_filmography_without_llm() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "что еще сняла Луна Сильвер?",
            authorization=None,
            session_id="sess-19",
        )
    )

    assert response.intent == "person_filmography"
    assert response.metadata["plan_source"] == "deterministic"
    assert "Фильмы режиссёра Луна Сильвер" in response.answer_text
    assert "Тихая Луна" in response.answer_text
    assert "Лунар: Серебряная звезда" in response.answer_text
    assert "Красный маяк" not in response.answer_text


def test_detects_filmy_s_uchastiem_without_llm() -> None:
    service, _, _, _, _ = build_service()

    response = asyncio.run(
        service.handle_query(
            "фильмы с участием Луна Сильвер",
            authorization=None,
            session_id="sess-20",
        )
    )

    assert response.intent == "person_filmography"
    assert response.metadata["plan_source"] == "deterministic"
    assert "У меня нет данных о фильмах с участием Луна Сильвер." == response.answer_text



def test_public_search_cards_fill_rating_from_film_details() -> None:
    service, _, catalog_client, _, _ = build_service()

    items = asyncio.run(service.public_search("Луна", authorization=None))

    by_title = {item["title"]: item for item in items}

    assert by_title["Тихая Луна"]["imdb_rating"] == catalog_client.film_details_map["film-1"]["imdb_rating"]
    assert by_title["Лунар: Серебряная звезда"]["imdb_rating"] == catalog_client.film_details_map["film-2"]["imdb_rating"]
