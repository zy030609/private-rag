"""
Private-RAG 通用私有文档问答系统 — FastAPI 应用入口

启动方式:
    python main.py                 # 直接运行
    uvicorn main:app --reload      # 开发模式热重载

环境变量配置请参考 .env.example 文件。
"""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from utils.logger import logger


@dataclass
class AppState:
    """Runtime objects shared by API routes through app.state."""

    vector_store: Any
    rag_graph: Any
    rag_service: Any
    document_service: Any
    knowledge_base_service: Any = None
    redis_cache: Any = None
    # 仅保留构造兼容性，不再初始化或注册原教育版服务。
    knowledge_service: Any = None
    analytics_service: Any = None


def init_vector_store_sync():
    """
    同步初始化向量存储（Milvus Lite）。
    """
    from core.vectorestore import PrivateDocumentVectorStore

    logger.info("正在初始化向量存储（同步）...")
    vs = PrivateDocumentVectorStore()
    stats = vs.collection_stats
    logger.info(f"向量存储就绪，当前数据量: {stats.get('row_count', 0)} 条")
    return vs


def init_rag_graph_sync(vector_store, redis_cache=None):
    """同步初始化 LangGraph 工作流"""
    from core.graph import build_rag_graph

    logger.info("正在构建 RAG 工作流...")
    graph = build_rag_graph(vector_store, retrieval_cache=redis_cache)
    logger.info("RAG 工作流构建完成")
    return graph


def build_app_state(vector_store: Any | None = None, rag_graph: Any | None = None) -> AppState:
    """Build all runtime services for the app."""
    from services.document_service import DocumentService
    from services.rag_service import RAGService
    from services.knowledge_base_service import KnowledgeBaseService
    from core.redis_cache import RedisRetrievalCache

    vector_store = vector_store or init_vector_store_sync()
    redis_cache = RedisRetrievalCache()
    rag_graph = rag_graph or init_rag_graph_sync(vector_store, redis_cache)
    return AppState(
        vector_store=vector_store,
        rag_graph=rag_graph,
        rag_service=RAGService(vector_store, rag_graph),
        document_service=DocumentService(vector_store, retrieval_cache=redis_cache),
        knowledge_base_service=KnowledgeBaseService(),
        redis_cache=redis_cache,
    )


def attach_app_state(app: FastAPI, state: AppState) -> None:
    """Attach runtime services to app.state."""
    app.state.vector_store = state.vector_store
    app.state.rag_graph = state.rag_graph
    app.state.rag_service = state.rag_service
    app.state.document_service = state.document_service
    app.state.knowledge_base_service = state.knowledge_base_service or __import__(
        "services.knowledge_base_service", fromlist=["KnowledgeBaseService"]
    ).KnowledgeBaseService()
    app.state.redis_cache = state.redis_cache


async def init_database():
    """初始化业务数据库"""
    from models.db_models import init_db

    logger.info("正在初始化业务数据库...")
    await init_db()
    logger.info("业务数据库就绪")


def register_routers(app: FastAPI) -> None:
    """注册 API 路由"""
    from api import documents, evaluation, knowledge_bases, rag
    # from api import analytics, knowledge  # 暂未开发完成，先隐藏

    app.include_router(rag.router)
    app.include_router(documents.router)
    app.include_router(knowledge_bases.router)
    # app.include_router(knowledge.router)   # 知识点模块暂未完成
    # app.include_router(analytics.router)   # 学情分析模块暂未完成
    app.include_router(evaluation.router)
    logger.info("API 路由注册完成")


def create_app(
    app_state: AppState | None = None,
    *,
    initialize_runtime: bool = True,
) -> FastAPI:
    """Create the FastAPI application without import-time heavy initialization."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("=========================================")
        logger.info("  Private-RAG 通用私有文档问答系统启动中...")
        logger.info(f"  Milvus 地址: {settings.MILVUS_URI}")
        logger.info(f"  Embedding 模型: {settings.EMBEDDING_MODEL}")
        logger.info(f"  LLM 模型: {settings.LLM_MODEL}")
        logger.info(f"  Redis 缓存: {'启用' if settings.REDIS_ENABLED else '关闭'}")
        logger.info(f"  日志级别: {settings.LOG_LEVEL}")
        logger.info("=========================================")

        if app_state is not None:
            attach_app_state(app, app_state)
        elif initialize_runtime:
            attach_app_state(app, build_app_state())

        if initialize_runtime:
            await init_database()

        logger.info("系统启动完成，等待请求...")
        yield
        logger.info("系统关闭中...")
        redis_cache = getattr(app.state, "redis_cache", None)
        if redis_cache is not None:
            await redis_cache.close()

    app = FastAPI(
        title="Private-RAG 私有文档问答系统",
        description="基于 FastAPI、LangGraph 与混合检索的多知识库私有文档问答系统。",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if app_state is not None:
        attach_app_state(app, app_state)

    @app.get("/")
    async def root():
        """返回 UI 界面"""
        html_path = os.path.join(os.path.dirname(__file__), "static", "private.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return {
            "app": "Private-RAG 私有文档问答系统",
            "version": "2.0.0",
            "status": "running",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health(request: Request):
        """健康检查接口"""
        try:
            vs = getattr(request.app.state, "vector_store", None)
            if vs is None:
                return {"status": "unhealthy", "error": "vector_store not initialized"}
            stats = vs.collection_stats
            return {
                "status": "healthy",
                "vector_store": stats,
                "llm_configured": bool(settings.LLM_API_KEY),
                "redis": await request.app.state.redis_cache.health()
                if getattr(request.app.state, "redis_cache", None) is not None
                else {"enabled": False, "connected": False},
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    register_routers(app)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    runtime_app = create_app(app_state=build_app_state())
    logger.info(f"启动服务器: {settings.APP_HOST}:{settings.APP_PORT}")
    uvicorn.run(
        runtime_app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )
