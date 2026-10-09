"""Shared state definitions for the RAG workflow."""

from typing import TypedDict


MAX_ROUNDS = 10


class RAGState(TypedDict):
    """RAG 流程的全局状态"""

    query: str
    knowledge_base_id: str
    session_id: str
    intent: str
    complexity: str
    retrieved_docs: list
    answer: str
    retry_count: int
    max_retries: int
    conversation_history: list[dict]
    retrieval_plan: dict
    retrieval_attempts: list[dict]
    retrieval_metrics: dict
    retrieval_decision: dict
    abstain_reason: str
    retrieval_latency_ms: float
    retrieval_cache_hit: bool
    rerank_latency_ms: float
    reranker_available: bool
    sub_queries: list[str]
    _queue_id: str


def build_initial_state(query: str, knowledge_base_id: str, session_id: str, max_retries: int) -> dict:
    """构造一次知识库问答的初始可序列化状态。"""
    return {
        "query": query,
        "knowledge_base_id": knowledge_base_id,
        "session_id": session_id,
        "intent": "",
        "complexity": "",
        "retrieved_docs": [],
        "answer": "",
        "retry_count": 0,
        "max_retries": max_retries,
        "retrieval_plan": {"strategy": "initial", "queries": [query]},
        "retrieval_attempts": [],
        "retrieval_metrics": {},
        "retrieval_decision": {},
        "retrieval_cache_hit": False,
        "abstain_reason": "",
        "sub_queries": [],
        "_queue_id": "",
    }
