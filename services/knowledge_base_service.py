"""知识库管理服务。"""

import uuid

from sqlalchemy import func, select

from models.db_models import Document, KnowledgeBase, get_session_maker


class KnowledgeBaseService:
    async def create(self, name: str, description: str = "") -> dict:
        session_maker = get_session_maker()
        async with session_maker() as session:
            knowledge_base = KnowledgeBase(
                id=str(uuid.uuid4()),
                name=name.strip(),
                description=description.strip(),
            )
            session.add(knowledge_base)
            await session.commit()
            return self._serialize(knowledge_base, document_count=0)

    async def list(self) -> list[dict]:
        session_maker = get_session_maker()
        async with session_maker() as session:
            rows = await session.execute(
                select(KnowledgeBase, func.count(Document.id))
                .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
                .group_by(KnowledgeBase.id)
                .order_by(KnowledgeBase.created_at.desc())
            )
            return [self._serialize(item, count) for item, count in rows.all()]

    async def exists(self, knowledge_base_id: str) -> bool:
        session_maker = get_session_maker()
        async with session_maker() as session:
            return await session.get(KnowledgeBase, knowledge_base_id) is not None

    async def delete(self, knowledge_base_id: str) -> bool:
        session_maker = get_session_maker()
        async with session_maker() as session:
            knowledge_base = await session.get(KnowledgeBase, knowledge_base_id)
            if knowledge_base is None:
                return False
            count = await session.scalar(
                select(func.count(Document.id)).where(Document.knowledge_base_id == knowledge_base_id)
            )
            if count:
                raise ValueError("请先删除知识库中的文档")
            await session.delete(knowledge_base)
            await session.commit()
            return True

    @staticmethod
    def _serialize(item: KnowledgeBase, document_count: int) -> dict:
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "document_count": int(document_count),
            "created_at": item.created_at.isoformat() if item.created_at else "",
        }
