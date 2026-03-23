from __future__ import annotations

import time
from typing import Any, Protocol

import orjson


class SessionStore(Protocol):
    async def load(self, session_id: str) -> dict[str, Any]: ...

    async def save(self, session_id: str, session: dict[str, Any]) -> None: ...


class ParseCacheStore(Protocol):
    async def load(self, cache_key: str) -> dict[str, Any] | None: ...

    async def save(self, cache_key: str, payload: dict[str, Any]) -> None: ...


class PublicResponseCacheStore(Protocol):
    async def load(self, cache_key: str) -> dict[str, Any] | None: ...

    async def save(self, cache_key: str, payload: dict[str, Any]) -> None: ...


class FeedbackStore(Protocol):
    async def record(self, event: dict[str, Any]) -> None: ...


class LlmCircuitStore(Protocol):
    async def is_open(self) -> bool: ...

    async def record_success(self) -> None: ...

    async def record_failure(self) -> None: ...


class RedisSessionStore:
    def __init__(
        self, redis: Any, ttl_seconds: int, key_prefix: str = "assistant_session"
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{session_id}"

    async def load(self, session_id: str) -> dict[str, Any]:
        raw = await self.redis.get(self._key(session_id))
        if raw is None:
            return {}
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        payload = orjson.loads(raw)
        return payload if isinstance(payload, dict) else {}

    async def save(self, session_id: str, session: dict[str, Any]) -> None:
        payload = {key: value for key, value in session.items() if value is not None}
        await self.redis.set(
            self._key(session_id), orjson.dumps(payload), ex=self.ttl_seconds
        )


class RedisJsonCacheStore:
    def __init__(self, redis: Any, ttl_seconds: int, key_prefix: str) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def _key(self, cache_key: str) -> str:
        return f"{self.key_prefix}:{cache_key}"

    async def load(self, cache_key: str) -> dict[str, Any] | None:
        raw = await self.redis.get(self._key(cache_key))
        if raw is None:
            return None
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        payload = orjson.loads(raw)
        return payload if isinstance(payload, dict) else None

    async def save(self, cache_key: str, payload: dict[str, Any]) -> None:
        await self.redis.set(
            self._key(cache_key), orjson.dumps(payload), ex=self.ttl_seconds
        )


class RedisParseCacheStore(RedisJsonCacheStore):
    pass


class RedisPublicResponseCacheStore(RedisJsonCacheStore):
    pass


class RedisFeedbackStore:
    def __init__(self, redis: Any, key_prefix: str, max_events: int = 5000) -> None:
        self.redis = redis
        self.key_prefix = key_prefix
        self.max_events = max_events

    @property
    def _events_key(self) -> str:
        return f"{self.key_prefix}:events"

    @property
    def _summary_key(self) -> str:
        return f"{self.key_prefix}:summary"

    async def record(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("recorded_at", int(time.time()))
        await self.redis.lpush(self._events_key, orjson.dumps(payload))
        await self.redis.ltrim(self._events_key, 0, self.max_events - 1)
        reaction = str(payload.get("reaction") or "unknown")
        await self.redis.hincrby(self._summary_key, reaction, 1)
        intent = str(payload.get("intent") or "unknown")
        await self.redis.hincrby(f"{self._summary_key}:intent:{intent}", reaction, 1)


class RedisLlmCircuitStore:
    def __init__(
        self, redis: Any, key_prefix: str, failure_threshold: int, cooldown_seconds: int
    ) -> None:
        self.redis = redis
        self.key_prefix = key_prefix
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    @property
    def _state_key(self) -> str:
        return f"{self.key_prefix}:llm_circuit"

    async def _load_state(self) -> dict[str, Any]:
        raw = await self.redis.get(self._state_key)
        if raw is None:
            return {"failures": 0, "open_until": 0}
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        payload = orjson.loads(raw)
        if not isinstance(payload, dict):
            return {"failures": 0, "open_until": 0}
        return {
            "failures": int(payload.get("failures", 0)),
            "open_until": int(payload.get("open_until", 0)),
        }

    async def _save_state(self, state: dict[str, Any]) -> None:
        ttl = max(self.cooldown_seconds, 60)
        await self.redis.set(self._state_key, orjson.dumps(state), ex=ttl)

    async def is_open(self) -> bool:
        state = await self._load_state()
        return int(state.get("open_until", 0)) > int(time.time())

    async def record_success(self) -> None:
        await self._save_state({"failures": 0, "open_until": 0})

    async def record_failure(self) -> None:
        state = await self._load_state()
        failures = int(state.get("failures", 0)) + 1
        open_until = int(state.get("open_until", 0))
        if failures >= self.failure_threshold:
            open_until = int(time.time()) + self.cooldown_seconds
            failures = 0
        await self._save_state({"failures": failures, "open_until": open_until})


class InMemoryJsonCacheStore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    async def load(self, cache_key: str) -> dict[str, Any] | None:
        payload = self.data.get(cache_key)
        return dict(payload) if payload is not None else None

    async def save(self, cache_key: str, payload: dict[str, Any]) -> None:
        self.data[cache_key] = dict(payload)


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def record(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


class InMemoryLlmCircuitStore:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.open_until = 0

    async def is_open(self) -> bool:
        return self.open_until > int(time.time())

    async def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0

    async def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.failures = 0
            self.open_until = int(time.time()) + self.cooldown_seconds


class NullJsonCacheStore:
    async def load(self, cache_key: str) -> dict[str, Any] | None:
        return None

    async def save(self, cache_key: str, payload: dict[str, Any]) -> None:
        return None


class NullFeedbackStore:
    async def record(self, event: dict[str, Any]) -> None:
        return None


class NullLlmCircuitStore:
    async def is_open(self) -> bool:
        return False

    async def record_success(self) -> None:
        return None

    async def record_failure(self) -> None:
        return None
