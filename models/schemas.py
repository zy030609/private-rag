"""Pydantic 数据模型：API 请求/响应 Schema"""

from pydantic import BaseModel, Field
from typing import Any


# ==================== 问答接口 ====================

class AskRequest(BaseModel):
    """问答请求"""
    query: str = Field(..., description="用户问题", min_length=1, max_length=2000)
    knowledge_base_id: str = Field(..., description="知识库 ID")
    user_id: str | None = Field(None, description="用户 ID")
    session_id: str | None = Field(None, description="会话 ID")
    stream: bool = Field(False, description="是否流式输出")


class Reference(BaseModel):
    """引用来源"""
    chunk_id: int | None = None
    document_id: str = ""
    text: str = ""
    source: str = ""
    score: float = 0.0
    knowledge_base_id: str = ""
    source_file: str = ""
    page: int = 0


class AskResponse(BaseModel):
    """问答响应"""
    code: int = 0
    message: str = "success"
    data: dict[str, Any] | None = None


# ==================== 文档管理接口 ====================

class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    code: int = 0
    message: str = "success"
    data: dict | None = None


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    code: int = 0
    data: list[dict] = []
    total: int = 0


# ==================== 知识库管理接口 ====================

class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""
    name: str = Field(..., min_length=1, max_length=128, description="知识库名称")
    description: str = Field("", max_length=1000, description="知识库描述")


class KnowledgeBaseResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict | list[dict] | None = None


# ==================== SQL 数据导入 ====================

class SQLImportRequest(BaseModel):
    """SQL 数据导入请求：提供数据库连接信息，由后端连接数据库流式读取"""
    db_url: str = Field(..., description="数据库连接串，如 mysql+pymysql://user:pass@host:3306/db")
    table_name: str = Field(..., description="源表名")
    knowledge_base_id: str = Field(..., description="目标知识库 ID")
    tags: list[str] = Field(default_factory=list, description="文档标签")
    field_map: dict[str, str] | None = Field(None, description="字段中文映射，如 {'name': '商品', 'price': '价格'}")
    id_column: str = Field("id", description="主键列名，用于游标分页")
    columns: list[str] | None = Field(None, description="需要查询的列，不传默认 SELECT *")
    where_clause: str = Field("", description="附加 WHERE 条件，如 status='active'")
    batch_size: int = Field(1000, description="每批读取行数")
    strategy: str = Field("recursive", description="切片策略 (recursive/semantic/markdown)")


class SQLImportResponse(BaseModel):
    """SQL 导入响应"""
    code: int = 0
    message: str = "success"
    data: dict | None = None
