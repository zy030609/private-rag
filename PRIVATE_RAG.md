# Private-RAG：通用私有文档问答系统

Private-RAG 是一个面向企业资料、论文、合同和产品手册的本地知识库问答系统。系统使用 FastAPI 提供 REST/SSE 接口，通过 LangGraph 编排检索、重排、质量门控、重试和答案生成流程。

## 核心能力

- 多知识库管理：文档、Milvus 向量和 BM25 候选均按 `knowledge_base_id` 隔离。
- 文档入库：支持 PDF、Markdown、TXT，以及递归、Markdown 标题和语义切片。
- 混合检索：Milvus 稠密检索 + BM25 稀疏检索 + RRF 融合。
- 结果重排：使用 CrossEncoder 对候选片段重新评分。
- 质量门控：低质量结果自动改写查询并重试，证据不足时拒答。
- 可追溯引用：返回文件名、页码、片段内容、文档 ID 和相关性分数。
- 流式问答：FastAPI SSE 逐步返回模型输出。
- 效果评估：保留 RAGAS 和检索指标评估能力。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
python main.py
```

启动后访问：

- Web 控制台：`http://localhost:8000/`
- OpenAPI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

首次使用时先创建知识库，再上传文档并提问。Embedding 和 Reranker 模型会在首次运行时下载。

## 主要 API

```text
POST   /api/v1/knowledge-bases
GET    /api/v1/knowledge-bases
DELETE /api/v1/knowledge-bases/{knowledge_base_id}

POST   /api/v1/documents/upload
GET    /api/v1/documents/list?knowledge_base_id=...
DELETE /api/v1/documents/{document_id}

POST   /api/v1/rag/ask
POST   /api/v1/rag/ask-stream
POST   /api/v1/rag/feedback
```

问答请求示例：

```json
{
  "query": "公司的差旅报销标准是什么？",
  "knowledge_base_id": "your-kb-id",
  "session_id": "demo-session"
}
```

引用数据示例：

```json
{
  "index": 1,
  "document_id": "doc-id",
  "source_file": "员工手册.pdf",
  "page": 12,
  "text": "……",
  "score": 0.87,
  "knowledge_base_id": "your-kb-id"
}
```

## 数据隔离设计

`knowledge_base_id` 会写入业务数据库中的文档记录和 Milvus chunk metadata。在线查询时，稠密检索通过 Milvus filter 限制知识库，BM25 召回也在融合前执行相同过滤，防止跨知识库内容进入生成上下文。

## 测试

```bash
pytest -q test/test_private_rag.py
```

测试覆盖请求契约、知识库作用域、引用元数据和通用查询路由。完整集成测试需要先安装 `requirements.txt` 中的依赖。
