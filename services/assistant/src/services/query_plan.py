from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from services.query_parser import detect_intent
from services.query_parser import extract_film_title_with_context
from services.query_parser import extract_person_name_with_context


@dataclass(slots=True)
class QueryPlan:
    intent: str
    confidence: float
    source: str
    film_title: str | None = None
    person_name: str | None = None
    search_queries: list[str] = field(default_factory=list)
    requires_auth: bool | None = None
    reason: str | None = None



def deterministic_plan(query: str, session: dict[str, Any]) -> QueryPlan:
    intent = detect_intent(query)
    plan = QueryPlan(intent=intent, confidence=0.72, source='deterministic')

    if intent in {'film_rating', 'film_director', 'film_duration', 'film_genres', 'film_overview'}:
        plan.film_title = extract_film_title_with_context(query, session)
        if plan.film_title:
            plan.search_queries = [plan.film_title]
        else:
            plan.confidence = 0.25
    elif intent in {'person_movie_count', 'person_filmography', 'recommend_by_person'}:
        plan.person_name = extract_person_name_with_context(query, session)
        if plan.person_name:
            plan.search_queries = [plan.person_name]
        else:
            plan.confidence = 0.25
    elif intent == 'recommend_general':
        plan.confidence = 0.85
    elif intent == 'bookmarks':
        plan.requires_auth = True
        plan.confidence = 0.95
    elif intent == 'recommend_by_genre':
        plan.requires_auth = True
        plan.confidence = 0.9
    elif intent == 'help':
        plan.confidence = 0.2
    return plan



def should_accept_deterministic_plan(plan: QueryPlan) -> bool:
    if plan.intent in {'bookmarks', 'recommend_by_genre', 'recommend_general'}:
        return True
    if plan.intent in {'film_rating', 'film_director', 'film_duration', 'film_genres', 'film_overview'}:
        return bool(plan.film_title)
    if plan.intent in {'person_movie_count', 'person_filmography', 'recommend_by_person'}:
        return bool(plan.person_name)
    return plan.intent != 'help'
