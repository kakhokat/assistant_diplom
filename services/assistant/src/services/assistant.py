from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from fastapi import status

from clients.auth_client import AuthClient
from clients.catalog_client import CatalogClient
from clients.llm_client import LocalLlmClient
from clients.ugc_client import UgcClient
from core.settings import settings
from core.text_tools import normalize_for_match
from domain.models import AssistantFeedbackRequest
from domain.models import AssistantFeedbackResponse
from domain.models import AssistantResponse
from services.entity_resolver import help_text
from services.entity_resolver import prepare_film_cards
from services.entity_resolver import remember
from services.query_handlers import handle_bookmarks
from services.query_handlers import handle_film_query
from services.query_handlers import handle_person_filmography
from services.query_handlers import handle_person_movie_count
from services.query_handlers import handle_recommend_by_genre
from services.query_handlers import handle_recommend_by_person
from services.query_handlers import handle_recommend_general
from services.query_parser import looks_like_film_followup
from services.query_parser import looks_like_person_followup
from services.query_plan import QueryPlan
from services.query_plan import deterministic_plan
from services.query_plan import should_accept_deterministic_plan
from services.session_store import FeedbackStore
from services.session_store import LlmCircuitStore
from services.session_store import NullFeedbackStore
from services.session_store import NullJsonCacheStore
from services.session_store import NullLlmCircuitStore
from services.session_store import ParseCacheStore
from services.session_store import PublicResponseCacheStore
from services.session_store import RedisFeedbackStore
from services.session_store import RedisLlmCircuitStore
from services.session_store import RedisParseCacheStore
from services.session_store import RedisPublicResponseCacheStore
from services.session_store import RedisSessionStore
from services.session_store import SessionStore


class AssistantService:
    def __init__(
        self,
        auth_client: AuthClient,
        catalog_client: CatalogClient,
        ugc_client: UgcClient,
        session_store: SessionStore,
        llm_client: LocalLlmClient | None = None,
        parse_cache: ParseCacheStore | None = None,
        public_response_cache: PublicResponseCacheStore | None = None,
        feedback_store: FeedbackStore | None = None,
        llm_circuit_store: LlmCircuitStore | None = None,
    ):
        self.auth_client = auth_client
        self.catalog_client = catalog_client
        self.ugc_client = ugc_client
        self.session_store = session_store
        self.llm_client = llm_client
        self.parse_cache = parse_cache or NullJsonCacheStore()
        self.public_response_cache = public_response_cache or NullJsonCacheStore()
        self.feedback_store = feedback_store or NullFeedbackStore()
        self.llm_circuit_store = llm_circuit_store or NullLlmCircuitStore()

    async def public_feed(self, limit: int, authorization: str | None) -> list[dict[str, Any]]:
        items = await self._catalog_list_top_films(authorization, limit=limit)
        return await prepare_film_cards(self, items, authorization)

    async def public_search(self, query: str, authorization: str | None) -> list[dict[str, Any]]:
        items = await self._catalog_search_films(query.strip(), authorization)
        return await prepare_film_cards(self, items, authorization)

    async def submit_feedback(self, payload: AssistantFeedbackRequest) -> AssistantFeedbackResponse:
        await self.feedback_store.record(
            {
                'session_id': payload.session_id,
                'query': payload.query,
                'normalized_query': normalize_for_match(payload.query),
                'reaction': payload.reaction,
                'intent': payload.intent or 'unknown',
                'metadata': payload.metadata,
            }
        )
        return AssistantFeedbackResponse(status='ok')

    async def handle_query(
        self,
        query: str,
        authorization: str | None,
        session_id: str | None = None,
    ) -> AssistantResponse:
        current_session_id = session_id or uuid4().hex
        session = await self.session_store.load(current_session_id)
        parse_cache_key = self._build_parse_cache_key(query, session)

        try:
            plan = await self._build_plan(query, session, parse_cache_key)

            if plan.intent == 'bookmarks':
                if not self._has_bearer(authorization):
                    response = self._auth_required_response(query, current_session_id, session, 'bookmarks')
                else:
                    response = await handle_bookmarks(self, query, authorization, current_session_id, session)
            elif plan.intent == 'recommend_by_genre':
                if not self._has_bearer(authorization):
                    response = self._auth_required_response(query, current_session_id, session, 'recommend_by_genre')
                else:
                    response = await handle_recommend_by_genre(self, query, authorization, current_session_id, session)
            elif plan.intent == 'recommend_general':
                response = await handle_recommend_general(self, query, authorization, current_session_id, session)
            elif plan.intent == 'recommend_by_person':
                response = await handle_recommend_by_person(
                    self,
                    query,
                    authorization,
                    current_session_id,
                    session,
                    person_name=plan.person_name,
                    search_queries=plan.search_queries,
                )
            elif plan.intent == 'person_movie_count':
                response = await handle_person_movie_count(
                    self,
                    query,
                    authorization,
                    current_session_id,
                    session,
                    person_name=plan.person_name,
                    search_queries=plan.search_queries,
                )
            elif plan.intent == 'person_filmography':
                response = await handle_person_filmography(
                    self,
                    query,
                    authorization,
                    current_session_id,
                    session,
                    person_name=plan.person_name,
                    search_queries=plan.search_queries,
                )
            elif plan.intent in {'film_rating', 'film_director', 'film_duration', 'film_genres', 'film_overview'}:
                response = await handle_film_query(
                    self,
                    plan.intent,
                    query,
                    authorization,
                    current_session_id,
                    session,
                    film_title=plan.film_title,
                    search_queries=plan.search_queries,
                )
            else:
                response = self._response(
                    query=query,
                    session_id=current_session_id,
                    intent='help',
                    answer_text=help_text(),
                    confidence=max(plan.confidence, 0.35),
                    used_services=[] if plan.source == 'deterministic' else ['llm'],
                    metadata={'reason': plan.reason},
                    context=session,
                )

            response.metadata['plan_source'] = plan.source
            response.metadata['parse_cache_key'] = parse_cache_key
            response.metadata['llm_fallback_used'] = plan.source in {'llm', 'parse_cache'}

            await self._maybe_store_public_response(response, authorization)
            await self.session_store.save(current_session_id, session)
            return response
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else 502
            detail = exc.response.text if exc.response is not None else str(exc)
            raise HTTPException(status_code=status_code, detail=f'upstream error: {detail}') from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'upstream connection error: {exc}') from exc

    async def _build_plan(self, query: str, session: dict[str, Any], parse_cache_key: str) -> QueryPlan:
        plan = deterministic_plan(query, session)
        if should_accept_deterministic_plan(plan):
            return plan

        cached_plan = await self.parse_cache.load(parse_cache_key)
        if cached_plan:
            return QueryPlan(
                intent=str(cached_plan.get('intent') or 'help'),
                confidence=float(cached_plan.get('confidence') or 0.5),
                source='parse_cache',
                film_title=cached_plan.get('film_title'),
                person_name=cached_plan.get('person_name'),
                search_queries=list(cached_plan.get('search_queries') or []),
                requires_auth=cached_plan.get('requires_auth'),
                reason=cached_plan.get('reason'),
            )

        if self.llm_client and self.llm_client.is_enabled():
            if await self.llm_circuit_store.is_open():
                plan.source = 'llm_circuit_open'
                plan.reason = 'llm circuit is open'
                return plan
            llm_plan = await self._llm_plan(query, session)
            if llm_plan is not None:
                await self.parse_cache.save(
                    parse_cache_key,
                    {
                        'intent': llm_plan.intent,
                        'confidence': llm_plan.confidence,
                        'film_title': llm_plan.film_title,
                        'person_name': llm_plan.person_name,
                        'search_queries': llm_plan.search_queries,
                        'requires_auth': llm_plan.requires_auth,
                        'reason': llm_plan.reason,
                    },
                )
                return llm_plan
        return plan

    async def _llm_plan(self, query: str, session: dict[str, Any]) -> QueryPlan | None:
        if not self.llm_client or not self.llm_client.is_enabled():
            return None
        parsed = await self.llm_client.parse_query(query, session)
        if parsed is None:
            await self.llm_circuit_store.record_failure()
            return None
        from core.capabilities import get_supported_intents

        if parsed.intent not in get_supported_intents():
            await self.llm_circuit_store.record_failure()
            return None
        await self.llm_circuit_store.record_success()
        return QueryPlan(
            intent=parsed.intent,
            confidence=parsed.confidence,
            source='llm',
            film_title=parsed.film_title,
            person_name=parsed.person_name,
            search_queries=[item for item in parsed.search_queries if item],
            requires_auth=parsed.requires_auth,
            reason=parsed.reason,
        )

    @staticmethod
    def _has_bearer(authorization: str | None) -> bool:
        if not authorization:
            return False
        value = authorization.strip()
        scheme, _, token = value.partition(' ')
        return scheme.lower() == 'bearer' and bool(token.strip())

    async def _catalog_authorization(self, authorization: str | None) -> tuple[str, bool]:
        if self._has_bearer(authorization):
            return str(authorization), False
        return await self.auth_client.service_authorization(), True

    async def _catalog_call(self, method_name: str, *args: Any, authorization: str | None, **kwargs: Any) -> Any:
        method = getattr(self.catalog_client, method_name)
        auth_header, _ = await self._catalog_authorization(authorization)
        try:
            return await method(*args, auth_header, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                refreshed_auth = await self.auth_client.service_authorization(force_refresh=True)
                return await method(*args, refreshed_auth, **kwargs)
            raise

    async def _catalog_search_films(self, query: str, authorization: str | None) -> list[dict[str, Any]]:
        return await self._catalog_call('search_films', query, authorization=authorization)

    async def _catalog_search_genres(self, query: str, authorization: str | None) -> list[dict[str, Any]]:
        return await self._catalog_call('search_genres', query, authorization=authorization)

    async def _catalog_list_top_films(self, authorization: str | None, limit: int = 10) -> list[dict[str, Any]]:
        return await self._catalog_call('list_top_films', authorization=authorization, limit=limit)

    async def _catalog_film_details(self, film_id: str, authorization: str | None) -> dict[str, Any]:
        return await self._catalog_call('film_details', film_id, authorization=authorization)

    async def _catalog_genre_details(self, genre_id: str, authorization: str | None) -> dict[str, Any]:
        return await self._catalog_call('genre_details', genre_id, authorization=authorization)

    async def _catalog_films_by_genre(self, genre_id: str, authorization: str | None) -> list[dict[str, Any]]:
        return await self._catalog_call('films_by_genre', genre_id, authorization=authorization)

    async def _catalog_search_persons(self, query: str, authorization: str | None) -> list[dict[str, Any]]:
        return await self._catalog_call('search_persons', query, authorization=authorization)

    async def _catalog_person_details(self, person_id: str, authorization: str | None) -> dict[str, Any]:
        return await self._catalog_call('person_details', person_id, authorization=authorization)

    async def _me_or_none(self, authorization: str | None) -> dict[str, Any] | None:
        try:
            return await self.auth_client.me(authorization)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                return None
            raise

    def _build_parse_cache_key(self, query: str, session: dict[str, Any]) -> str:
        parts = [settings.ASSISTANT_PARSE_CACHE_VERSION, normalize_for_match(query)]
        if looks_like_film_followup(query) and session.get('film_title'):
            parts.append(f"film={normalize_for_match(str(session['film_title']))}")
        if looks_like_person_followup(query) and session.get('person_name'):
            parts.append(f"person={normalize_for_match(str(session['person_name']))}")
        return '|'.join(item for item in parts if item)

    @staticmethod
    def _public_response_cache_key(intent: str, *, entity_type: str, entity_id: str) -> str:
        return f'{intent}|{entity_type}|{entity_id}'

    async def _load_cached_public_response(
        self,
        cache_key: str,
        query: str,
        session_id: str,
        session: dict[str, Any],
    ) -> AssistantResponse | None:
        cached_payload = await self.public_response_cache.load(cache_key)
        if not cached_payload:
            return None
        cached_response = AssistantResponse.model_validate(cached_payload)
        remember(session, cached_response.context)
        metadata = dict(cached_response.metadata)
        metadata['response_cache_hit'] = True
        return AssistantResponse(
            query=query,
            session_id=session_id,
            intent=cached_response.intent,
            answer=cached_response.answer,
            answer_text=cached_response.answer_text,
            speak_text=cached_response.speak_text,
            requires_auth=cached_response.requires_auth,
            confidence=cached_response.confidence,
            used_services=list(cached_response.used_services),
            metadata=metadata,
            context=dict(session),
            result=cached_response.result,
            alternatives=list(cached_response.alternatives),
        )

    async def _maybe_store_public_response(self, response: AssistantResponse, authorization: str | None) -> None:
        if self._has_bearer(authorization):
            return
        cache_key = str(response.metadata.get('public_response_cache_key') or '')
        if not cache_key:
            return
        await self.public_response_cache.save(cache_key, response.model_dump())

    def _auth_required_response(
        self,
        query: str,
        session_id: str,
        context: dict[str, Any],
        intent: str,
    ) -> AssistantResponse:
        return self._response(
            query=query,
            session_id=session_id,
            intent=intent,
            answer_text='Для этого запроса нужно войти в систему. После входа я смогу показать персональные данные.',
            confidence=0.95,
            used_services=[],
            metadata={},
            context=dict(context),
            requires_auth=True,
        )

    @staticmethod
    def _response(
        *,
        query: str,
        session_id: str,
        intent: str,
        answer_text: str,
        confidence: float,
        used_services: list[str],
        metadata: dict[str, Any],
        context: dict[str, Any],
        result: Any = None,
        alternatives: list[dict[str, Any]] | None = None,
        requires_auth: bool = False,
        speak_text: str | None = None,
    ) -> AssistantResponse:
        normalized_speak = speak_text or answer_text
        return AssistantResponse(
            query=query,
            session_id=session_id,
            intent=intent,
            answer=answer_text,
            answer_text=answer_text,
            speak_text=normalized_speak,
            requires_auth=requires_auth,
            confidence=confidence,
            used_services=used_services,
            metadata=metadata,
            context=dict(context),
            result=result,
            alternatives=alternatives or [],
        )



def build_assistant_service(client: httpx.AsyncClient, session_redis: Any) -> AssistantService:
    llm_client = LocalLlmClient(client)
    session_store = RedisSessionStore(
        redis=session_redis,
        ttl_seconds=settings.ASSISTANT_SESSION_TTL_SECONDS,
        key_prefix=settings.ASSISTANT_SESSION_KEY_PREFIX,
    )
    parse_cache = RedisParseCacheStore(
        redis=session_redis,
        ttl_seconds=settings.ASSISTANT_PARSE_CACHE_TTL_SECONDS,
        key_prefix=settings.ASSISTANT_PARSE_CACHE_KEY_PREFIX,
    )
    public_response_cache = RedisPublicResponseCacheStore(
        redis=session_redis,
        ttl_seconds=settings.ASSISTANT_PUBLIC_RESPONSE_CACHE_TTL_SECONDS,
        key_prefix=settings.ASSISTANT_PUBLIC_RESPONSE_CACHE_KEY_PREFIX,
    )
    feedback_store = RedisFeedbackStore(
        redis=session_redis,
        key_prefix=settings.ASSISTANT_FEEDBACK_KEY_PREFIX,
        max_events=settings.ASSISTANT_FEEDBACK_MAX_EVENTS,
    )
    llm_circuit_store = RedisLlmCircuitStore(
        redis=session_redis,
        key_prefix=settings.ASSISTANT_FEEDBACK_KEY_PREFIX,
        failure_threshold=settings.ASSISTANT_LLM_FAILURE_THRESHOLD,
        cooldown_seconds=settings.ASSISTANT_LLM_COOLDOWN_SECONDS,
    )
    return AssistantService(
        auth_client=AuthClient(client),
        catalog_client=CatalogClient(client),
        ugc_client=UgcClient(client),
        session_store=session_store,
        llm_client=llm_client,
        parse_cache=parse_cache,
        public_response_cache=public_response_cache,
        feedback_store=feedback_store,
        llm_circuit_store=llm_circuit_store,
    )
