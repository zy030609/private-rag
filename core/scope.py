"""知识库作用域规则。"""


def require_knowledge_base_id(knowledge_base_id: str | None) -> str:
    value = (knowledge_base_id or "").strip()
    if not value:
        raise ValueError("knowledge_base_id 不能为空")
    return value


def belongs_to_knowledge_base(document: dict, knowledge_base_id: str) -> bool:
    """严格相等匹配，避免子串判断造成跨知识库数据泄漏。"""
    return document.get("knowledge_base_id", "") == knowledge_base_id
