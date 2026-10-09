"""Private-RAG 通用化改造的轻量回归测试。"""

import pytest
from pydantic import ValidationError

from core.scope import belongs_to_knowledge_base, require_knowledge_base_id
from core.state import build_initial_state
from models.schemas import AskRequest
from utils.references import format_references


def test_ask_request_requires_knowledge_base_id():
    with pytest.raises(ValidationError):
        AskRequest(query="合同的有效期是多久？")

    payload = AskRequest(query="合同的有效期是多久？", knowledge_base_id="kb-1")
    assert payload.knowledge_base_id == "kb-1"


def test_initial_state_is_scoped_to_knowledge_base():
    state = build_initial_state("测试问题", "kb-private", "session-1", 2)
    assert state["knowledge_base_id"] == "kb-private"
    assert "subject" not in state
    assert "grade" not in state


def test_reference_contains_traceable_source_metadata():
    refs = format_references([
        {
            "id": 7,
            "doc_id": "doc-1",
            "knowledge_base_id": "kb-1",
            "source_file": "员工手册.pdf",
            "page": 12,
            "text": "试用期为三个月。",
            "rerank_score": 0.87654,
            "tags": ["人事"],
        }
    ])
    assert refs[0]["source_file"] == "员工手册.pdf"
    assert refs[0]["page"] == 12
    assert refs[0]["knowledge_base_id"] == "kb-1"
    assert refs[0]["score"] == 0.8765


def test_bm25_scope_uses_strict_equality():
    assert belongs_to_knowledge_base({"knowledge_base_id": "kb-1"}, "kb-1")
    assert not belongs_to_knowledge_base({"knowledge_base_id": "kb-10"}, "kb-1")
    with pytest.raises(ValueError):
        require_knowledge_base_id("  ")
