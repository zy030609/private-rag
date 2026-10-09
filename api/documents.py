"""文档管理接口：上传、列表、删除文档，支持文件(PDF/MD/TXT)和SQL数据导入"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from models.schemas import (
    DocumentUploadResponse,
    DocumentListResponse,
    SQLImportRequest,
    SQLImportResponse,
)
from utils.logger import logger

router = APIRouter(prefix="/api/v1/documents", tags=["文档管理"])


def get_document_service(request: Request):
    service = getattr(request.app.state, "document_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="文档服务未初始化")
    return service


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="待上传的文件"),
    knowledge_base_id: str = Form(..., description="知识库 ID"),
    tags: str = Form("", description="逗号分隔的标签"),
    strategy: str = Form("recursive", description="切片策略"),
):
    """上传文档并自动处理入库（PDF/MD/TXT）"""
    document_service = get_document_service(request)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    allowed_ext = (".pdf", ".md", ".txt")
    if not any(file.filename.lower().endswith(ext) for ext in allowed_ext):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持: {allowed_ext}")

    logger.info(f"上传文档: {file.filename}, knowledge_base_id={knowledge_base_id}")

    try:
        content = await file.read()
        result = await document_service.upload_and_process(
            file_content=content,
            filename=file.filename,
            knowledge_base_id=knowledge_base_id,
            tags=[item.strip() for item in tags.split(",") if item.strip()],
            strategy=strategy,
        )
        return DocumentUploadResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"文档上传处理失败: {e}")
        return DocumentUploadResponse(code=500, message=f"处理失败: {str(e)}")


@router.post("/import/sql", response_model=SQLImportResponse)
async def import_sql(req: SQLImportRequest, request: Request):
    """从 SQL 数据库导入：后端连接数据库 → 流式读取 → 清洗 → 切片 → 入库"""
    document_service = get_document_service(request)

    if not req.db_url:
        raise HTTPException(status_code=400, detail="db_url 不能为空")

    if not req.table_name:
        raise HTTPException(status_code=400, detail="table_name 不能为空")

    logger.info(f"SQL 导入: table={req.table_name}, knowledge_base_id={req.knowledge_base_id}, db={req.db_url.split('@')[-1] if '@' in req.db_url else req.db_url}")

    try:
        result = await document_service.import_from_sql(
            db_url=req.db_url,
            table_name=req.table_name,
            knowledge_base_id=req.knowledge_base_id,
            tags=req.tags,
            field_map=req.field_map,
            id_column=req.id_column,
            columns=req.columns,
            where_clause=req.where_clause,
            batch_size=req.batch_size,
            strategy=req.strategy,
        )
        return SQLImportResponse(data=result)
    except Exception as e:
        logger.error(f"SQL 导入失败: {e}")
        return SQLImportResponse(code=500, message=f"导入失败: {str(e)}")


@router.get("/list", response_model=DocumentListResponse)
async def list_documents(request: Request, knowledge_base_id: str | None = None):
    """获取文档列表"""
    document_service = get_document_service(request)
    docs = await document_service.list_documents(knowledge_base_id)
    return DocumentListResponse(data=docs, total=len(docs))


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, request: Request):
    """删除文档及其向量数据"""
    document_service = get_document_service(request)
    success = await document_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 0, "message": "删除成功"}
