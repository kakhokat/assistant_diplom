from __future__ import annotations

import json
from typing import Any

import httpx

from core.capabilities import get_capabilities
from core.settings import settings
from domain.llm_models import LlmParseResult


class LocalLlmClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @staticmethod
    def is_enabled() -> bool:
        return (
            settings.ASSISTANT_LLM_ENABLED
            and settings.ASSISTANT_LLM_PROVIDER.lower() == "ollama"
        )

    async def parse_query(
        self, query: str, session_context: dict[str, Any]
    ) -> LlmParseResult | None:
        if not self.is_enabled():
            return None

        prompt = self._build_prompt(query, session_context)
        schema = {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "film_title": {"type": ["string", "null"]},
                "person_name": {"type": ["string", "null"]},
                "search_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 5,
                },
                "requires_auth": {"type": ["boolean", "null"]},
                "reason": {"type": ["string", "null"]},
            },
            "required": [
                "intent",
                "confidence",
                "film_title",
                "person_name",
                "search_queries",
                "requires_auth",
                "reason",
            ],
            "additionalProperties": False,
        }

        try:
            response = await self.client.post(
                f"{settings.ASSISTANT_LLM_BASE_URL}/api/generate",
                json={
                    "model": settings.ASSISTANT_LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": schema,
                },
                timeout=settings.ASSISTANT_LLM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            raw = response.json().get("response", "{}")
            payload = json.loads(raw)
            return LlmParseResult.model_validate(payload)
        except Exception:
            return None

    @staticmethod
    def _build_prompt(query: str, session_context: dict[str, Any]) -> str:
        capabilities = get_capabilities()
        intents = capabilities.get("intents", [])
        intents_text = []
        for item in intents:
            intents_text.append(
                json.dumps(
                    {
                        "name": item["name"],
                        "requires_auth": item["requires_auth"],
                        "description": item["description"],
                        "examples": item["examples"],
                    },
                    ensure_ascii=False,
                )
            )

        system_rules = {
            "task": "Преобразуй пользовательский запрос к кино-ассистенту в строгий JSON.",
            "rules": [
                "Выбирай только один intent из списка.",
                "Если запрос о фильме — заполни film_title.",
                "Если запрос о человеке — заполни person_name.",
                "Если пользователь спрашивает абстрактно вроде «посоветуй фильм» — выбирай recommend_general.",
                "Если пользователь спрашивает о своих данных вроде закладок или любимых жанров — сохрани requires_auth=true.",
                "Если распознана русская речь с англоязычным названием, постарайся вернуть canonical title в film_title и варианты в search_queries.",
                "Если запрос непонятен, возвращай intent=help.",
                "Ответ должен быть только JSON по схеме.",
            ],
        }

        return (
            f"SYSTEM_RULES:\n{json.dumps(system_rules, ensure_ascii=False, indent=2)}\n\n"
            f"SUPPORTED_INTENTS:\n{chr(10).join(intents_text)}\n\n"
            f"SESSION_CONTEXT:\n{json.dumps(session_context, ensure_ascii=False, indent=2)}\n\n"
            f"USER_QUERY:\n{query}\n"
        )
