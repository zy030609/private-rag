"""Redis-backed retrieval cache with safe degradation.

Redis is an acceleration layer only: every public method catches connection
errors so a Redis outage never makes the RAG workflow unavailable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import settings
from utils.logger import logger


class RedisRetrievalCache:
    """Cache retrieval candidates and invalidate them by knowledge-base version."""

    def __init__(
        self,
        *,
        url: str | None = None,
        ttl_seconds: int | None = None,
        enabled: bool | None = None,
        client: Any | None = None,
    ):
        self.enabled = settings.REDIS_ENABLED if enabled is None else enabled
        self.ttl_seconds = ttl_seconds or settings.REDIS_CACHE_TTL
        self.prefix = settings.REDIS_KEY_PREFIX
        self._client = client
        if self.enabled and self._client is None:
            try:
                self._client = Redis.from_url(
                    url or settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                )
            except (RedisError, OSError, ValueError) as exc:
                logger.warning("Redis 客户端初始化失败，缓存已降级关闭: %s", exc)
                self._client = None

    def _version_key(self, knowledge_base_id: str) -> str:
        return f"{self.prefix}:kb:{knowledge_base_id}:version"

    async def _knowledge_base_version(self, knowledge_base_id: str) -> str:
        value = await self._client.get(self._version_key(knowledge_base_id))
        return str(value or "0")

    async def _retrieval_key(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        complexity: str,
        retrieval_plan: dict,
        candidate_top_k: int,
    ) -> str:
        version = await self._knowledge_base_version(knowledge_base_id)
        payload = {
            "knowledge_base_id": knowledge_base_id,
            "version": version,
            "query": " ".join(query.strip().lower().split()),
            "complexity": complexity,
            "retrieval_plan": retrieval_plan,
            "candidate_top_k": candidate_top_k,
            "embedding_model": settings.EMBEDDING_MODEL,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"{self.prefix}:retrieval:{knowledge_base_id}:{digest}"

    async def get_retrieval(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        complexity: str,
        retrieval_plan: dict,
        candidate_top_k: int,
    ) -> dict | None:
        if not self.enabled or self._client is None:
            return None
        try:
            key = await self._retrieval_key(
                knowledge_base_id=knowledge_base_id,
                query=query,
                complexity=complexity,
                retrieval_plan=retrieval_plan,
                candidate_top_k=candidate_top_k,
            )
            raw = await self._client.get(key)
            if not raw:
                return None
            value = json.loads(raw)
            if not isinstance(value, dict):
                return None
            logger.info("Redis 检索缓存命中: knowledge_base_id=%s", knowledge_base_id)
            return value
        except (RedisError, OSError, ValueError, TypeError) as exc:
            logger.warning("读取 Redis 检索缓存失败，降级为正常检索: %s", exc)
            return None

    async def set_retrieval(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        complexity: str,
        retrieval_plan: dict,
        candidate_top_k: int,
        documents: list[dict],
        sub_queries: list[str],
    ) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            key = await self._retrieval_key(
                knowledge_base_id=knowledge_base_id,
                query=query,
                complexity=complexity,
                retrieval_plan=retrieval_plan,
                candidate_top_k=candidate_top_k,
            )
            payload = json.dumps(
                {"documents": documents, "sub_queries": sub_queries},
                ensure_ascii=False,
                default=str,
            )
            await self._client.set(key, payload, ex=self.ttl_seconds)
            logger.debug("Redis 检索缓存写入: key=%s, documents=%d", key, len(documents))
            return True
        except (RedisError, OSError, ValueError, TypeError) as exc:
            logger.warning("写入 Redis 检索缓存失败，不影响本次问答: %s", exc)
            return False

    async def bump_knowledge_base_version(self, knowledge_base_id: str) -> int | None:
        """Invalidate cached retrieval results after a successful document change."""
        if not self.enabled or self._client is None:
            return None
        try:
            version = int(await self._client.incr(self._version_key(knowledge_base_id)))
            logger.info(
                "Redis 知识库缓存版本已更新: knowledge_base_id=%s, version=%d",
                knowledge_base_id,
                version,
            )
            return version
        except (RedisError, OSError, ValueError, TypeError) as exc:
            logger.warning("更新 Redis 知识库版本失败，不影响文档操作: %s", exc)
            return None

    async def health(self) -> dict:
        if not self.enabled or self._client is None:
            return {"enabled": False, "connected": False}
        try:
            return {"enabled": True, "connected": bool(await self._client.ping())}
        except (RedisError, OSError, ValueError) as exc:
            return {"enabled": True, "connected": False, "error": str(exc)}

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "aclose"):
            try:
                await self._client.aclose()
            except (RedisError, OSError) as exc:
                logger.warning("关闭 Redis 客户端失败: %s", exc)
