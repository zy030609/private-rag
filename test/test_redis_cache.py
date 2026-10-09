import asyncio

from core.redis_cache import RedisRetrievalCache


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        return True

    async def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = str(value)
        return value

    async def ping(self):
        return True

    async def aclose(self):
        return None


def test_retrieval_cache_round_trip_and_version_invalidation():
    asyncio.run(_assert_retrieval_cache_round_trip_and_version_invalidation())


async def _assert_retrieval_cache_round_trip_and_version_invalidation():
    client = FakeRedis()
    cache = RedisRetrievalCache(client=client, enabled=True, ttl_seconds=60)
    request = {
        "knowledge_base_id": "kb-1",
        "query": "差旅住宿标准",
        "complexity": "medium",
        "retrieval_plan": {"strategy": "initial", "queries": ["差旅住宿标准"]},
        "candidate_top_k": 20,
    }

    assert await cache.get_retrieval(**request) is None
    assert await cache.set_retrieval(
        **request,
        documents=[{"id": 1, "text": "一线城市每晚 600 元"}],
        sub_queries=[],
    )
    cached = await cache.get_retrieval(**request)
    assert cached == {
        "documents": [{"id": 1, "text": "一线城市每晚 600 元"}],
        "sub_queries": [],
    }

    assert await cache.bump_knowledge_base_version("kb-1") == 1
    assert await cache.get_retrieval(**request) is None


def test_disabled_cache_is_a_noop():
    asyncio.run(_assert_disabled_cache_is_a_noop())


async def _assert_disabled_cache_is_a_noop():
    cache = RedisRetrievalCache(client=FakeRedis(), enabled=False)
    assert await cache.health() == {"enabled": False, "connected": False}
    assert await cache.bump_knowledge_base_version("kb-1") is None


def test_retrieve_node_uses_cached_candidates_without_vector_search():
    asyncio.run(_assert_retrieve_node_uses_cached_candidates_without_vector_search())


async def _assert_retrieve_node_uses_cached_candidates_without_vector_search():
    from core.graph import retrieve_node

    class CacheHit:
        async def get_retrieval(self, **kwargs):
            return {"documents": [{"id": 7, "text": "缓存片段"}], "sub_queries": []}

    class StoreMustNotRun:
        def hybrid_search(self, *args, **kwargs):
            raise AssertionError("cache hit must skip vector search")

    state = {
        "query": "差旅标准",
        "knowledge_base_id": "kb-1",
        "complexity": "simple",
        "retrieval_plan": {"strategy": "initial", "queries": ["差旅标准"]},
    }
    result = await retrieve_node(state, StoreMustNotRun(), CacheHit())
    assert result["retrieval_cache_hit"] is True
    assert result["retrieved_docs"][0]["text"] == "缓存片段"
