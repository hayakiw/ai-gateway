"""Mapping table storage using Redis."""

import json
import uuid

import redis.asyncio as redis

from app.config import settings


class MappingStore:
    """Stores PII mapping tables in Redis with TTL."""

    def __init__(self) -> None:
        self._redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    def _key(self, request_id: str) -> str:
        return f"pii_mapping:{request_id}"

    async def save(self, mapping: dict[str, str]) -> str:
        """Save mapping and return a request_id."""
        request_id = str(uuid.uuid4())
        await self._redis.set(
            self._key(request_id),
            json.dumps(mapping, ensure_ascii=False),
            ex=settings.redis_mapping_ttl,
        )
        return request_id

    async def load(self, request_id: str) -> dict[str, str] | None:
        """Load mapping by request_id. Returns None if expired or not found."""
        data = await self._redis.get(self._key(request_id))
        if data is None:
            return None
        return json.loads(data)

    async def delete(self, request_id: str) -> None:
        """Delete mapping."""
        await self._redis.delete(self._key(request_id))

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._redis.aclose()
