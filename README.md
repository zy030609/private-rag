# Private-RAG：通用私有文档问答系统

Private-RAG 是一个面向企业资料、论文、合同和产品手册的本地知识库问答系统。系统使用 FastAPI 提供 REST/SSE 接口，通过 LangGraph 编排检索、重排、质量门控、重试与答案生成流程。

## 核心能力

- **多知识库隔离**：业务数据、Milvus 稠密召回和 BM25 稀疏召回均按 `knowledge_base_id` 隔离。
- **多格式入库**：支持 PDF、Markdown、TXT，以及递归、Markdown 标题和语义切片。
- **混合检索**：Milvus 向量检索 + BM25 关键词检索 + RRF 候选融合。
- **Redis 检索缓存**：按知识库版本缓存检索候选，文档变化后自动失效，Redis 故障时自动降级。
- **重排与门控**：CrossEncoder 重排；低质量结果自动重试，证据不足时拒答。
- **复杂问题处理**：支持查询拆解、子问题感知重排、子答案生成与最终合成。
- **可追溯引用**：答案返回文件名、页码、片段、文档 ID 和相关性分数。
- **流式问答**：FastAPI SSE 逐步推送回答与最终引用元数据。
- **效果评估**：保留 RAGAS 答案评估和检索指标评估能力。

## 系统流程

```text
用户问题 + knowledge_base_id
        │
        ▼
查询复杂度判断
        │
        ▼
Redis 检索缓存（命中则跳过召回）
        │ 未命中
        ▼
Milvus 稠密检索 ─┐
                  ├─ RRF 融合 ─ CrossEncoder 重排 ─ 质量门控
BM25 稀疏检索 ───┘                              │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                            生成回答          查询改写重试          拒答
                              │
                              ▼
                       答案 + 来源引用
```

## 快速开始

推荐 Python 3.11–3.13。Milvus Lite 官方不支持原生 Windows；Windows 演示请先用 Docker 启动 Milvus Standalone，并在 `.env` 中设置 `PRIVATE_RAG_MILVUS_URI=http://localhost:19530`。

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
python main.py
```

Windows + PyCharm 的完整配置和面试演示步骤见 [PYCHARM_DEMO.md](PYCHARM_DEMO.md)。

Docker 环境可在项目根目录启动：

```bash
docker compose up -d
```

其中包括 Milvus Standalone、etcd、MinIO 和 Redis。Windows 下所有相对路径数据都会保存在项目所在磁盘的 `docker/volumes` 中。

启动后访问：

- Web 控制台：`http://localhost:8000/`
- OpenAPI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

首次使用时先创建知识库，再上传文档并提问。Embedding 和 Reranker 模型会在首次运行时下载。

## API

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

创建知识库：

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H "Content-Type: application/json" \
  -d '{"name":"公司制度库","description":"内部制度与员工手册"}'
```

上传文档：

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@员工手册.pdf" \
  -F "knowledge_base_id=<knowledge-base-id>" \
  -F "tags=人事,制度" \
  -F "strategy=recursive"
```

问答请求：

```json
{
  "query": "公司的差旅报销标准是什么？",
  "knowledge_base_id": "your-kb-id",
  "session_id": "demo-session"
}
```

响应的 `data.cache_hit` 表示本次是否命中 Redis 检索缓存：

```json
{"data": {"answer": "……", "references": [], "cache_hit": true}}
```

同一知识库、版本、问题与检索计划第二次执行时，`cache_hit` 会变为 `true`。缓存的是检索候选，不是最终答案，因此不会跳过 LLM 生成或破坏会话上下文。

引用数据：

```json
{
  "index": 1,
  "chunk_id": 42,
  "document_id": "doc-id",
  "source_file": "员工手册.pdf",
  "page": 12,
  "text": "……",
  "score": 0.87,
  "knowledge_base_id": "your-kb-id"
}
```

## 数据隔离

`knowledge_base_id` 会写入业务数据库的文档记录和 Milvus chunk metadata：

- 稠密检索通过 Milvus filter 限制知识库。
- BM25 使用进程内全量索引，但在候选融合前执行严格相等过滤。
- 上传和问答接口会校验知识库是否存在。
- 删除非空知识库返回 `409 Conflict`，防止产生孤立文档和向量。

## 测试

```bash
pytest -q test/test_private_rag.py
```

测试覆盖请求契约、知识库作用域、引用元数据与通用查询路由。完整测试需要先安装 `requirements.txt` 中的依赖。


