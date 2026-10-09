"""通用知识库管理接口。"""

from fastapi import APIRouter, HTTPException, Request

from models.schemas import KnowledgeBaseCreate, KnowledgeBaseResponse


router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["知识库管理"])


def _service(request: Request):
    service = getattr(request.app.state, "knowledge_base_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="知识库服务未初始化")
    return service


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(payload: KnowledgeBaseCreate, request: Request):
    return KnowledgeBaseResponse(data=await _service(request).create(payload.name, payload.description))


@router.get("", response_model=KnowledgeBaseResponse)
async def list_knowledge_bases(request: Request):
    return KnowledgeBaseResponse(data=await _service(request).list())


@router.delete("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def delete_knowledge_base(knowledge_base_id: str, request: Request):
    try:
        deleted = await _service(request).delete(knowledge_base_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return KnowledgeBaseResponse(message="删除成功")
