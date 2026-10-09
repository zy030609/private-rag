"""与运行时依赖无关的引用格式化工具。"""


def format_references(docs: list[dict]) -> list[dict]:
    """将检索片段转换为稳定、可追溯的 API 引用结构。"""
    references = []
    for doc in docs:
        references.append({
            "index": len(references) + 1,
            "chunk_id": doc.get("id"),
            "document_id": doc.get("doc_id", ""),
            "text": doc.get("text", "")[:200],
            "source_file": doc.get("source_file") or doc.get("doc_id") or "未知来源",
            "page": doc.get("page", 0),
            "knowledge_base_id": doc.get("knowledge_base_id", ""),
            "tags": doc.get("tags", []),
            "score": round(
                doc.get("rerank_score", doc.get("fusion_score", doc.get("score", 0))),
                4,
            ),
            "source": doc.get("doc_id", ""),
        })
    return references
