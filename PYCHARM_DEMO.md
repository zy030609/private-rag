# Private-RAG：PyCharm 学习与面试演示手册

这份手册按“先理解、再运行、最后能讲”的顺序编写。不要一开始背类名；先记住项目解决的问题：**让用户只基于自己上传的私有文档提问，并且答案带可核验的来源。**

## 1. 你需要先懂的 RAG

普通大模型只依赖训练时学到的内容，可能不知道公司的内部制度，也可能编造答案。RAG（Retrieval-Augmented Generation，检索增强生成）先从指定知识库找证据，再把“问题 + 证据”交给大模型回答。

本项目的一次请求可以简化为：

```text
创建知识库 -> 上传文件 -> 清洗/切片 -> 向量化并写入 Milvus
                                      |
用户提问 -> 复杂度判断 -> 混合检索 -> 重排 -> 质量门控
                                      |
                         通过 -> LLM 生成 -> 答案 + 引用
                         不通过 -> 改写重试 -> 仍不足则拒答
```

关键术语：

- Embedding：把文本变成向量，使意思相近的文本在向量空间中更接近。
- 稠密检索：使用 Embedding + Milvus，擅长语义相似。
- BM25：基于词频的稀疏检索，擅长精确关键词、编号和专有名词。
- RRF：按两路结果的排名进行融合，避免直接比较不同量纲的原始分数。
- CrossEncoder：同时阅读问题和候选片段，给候选做更精确的二次排序。
- 质量门控：证据分数过低时不生成答案，先改写查询重试，最终可拒答。
- LangGraph：把分类、检索、重排、重试和生成组织成有状态、可分支的工作流。
- SSE：服务器持续向浏览器推送回答片段，实现流式显示。

## 2. 从哪里读代码

按下面顺序阅读，每次只回答一个问题：

1. `main.py`：应用怎么创建、服务何时初始化、路由在哪里注册？
2. `api/knowledge_bases.py`：知识库 API 怎样接收请求？
3. `api/documents.py` -> `services/document_service.py` -> `ingestion/pipeline.py`：文件怎样入库？
4. `api/rag.py` -> `services/rag_service.py`：一次问答怎样进入工作流？
5. `core/graph.py`：节点、边和重试分支怎样连接？这是面试讲解的中心。
6. `core/nodes/retriever.py` -> `core/vectorestore.py`：混合检索和 RRF 怎样实现？
7. `core/reranker.py` -> `core/retrieval_quality.py`：怎样重排、决定接受/重试/拒答？
8. `core/nodes/generator.py`：上下文怎样拼接并流式生成？
9. `utils/references.py`：答案引用怎样变成前端可用的数据？
10. `test/test_private_rag.py`：项目最重要的行为约束是什么？

## 3. Windows 运行前提

需要：

- Python 3.11–3.13；
- Docker Desktop，用来运行 Milvus Standalone；
- Ollama 或其他兼容 OpenAI API 的模型服务；
- 首次安装依赖和 HuggingFace 模型时可联网。

本机快速演示可使用较小的 Ollama 模型；正式效果展示建议使用能力更好的模型。模型名必须与 `ollama list` 中完全一致。

在项目根目录创建 `.env`，Windows 推荐配置：

```dotenv
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2:0.5b
PRIVATE_RAG_MILVUS_URI=http://localhost:19530
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
ENABLE_RERANKER=false
RETRIEVAL_GATE_MODE=observe
HF_ENDPOINT=https://hf-mirror.com
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO
```

`ENABLE_RERANKER=false` 配合 `RETRIEVAL_GATE_MODE=observe` 适合第一次快速跑通，省去下载较大的重排模型。此时系统会放行召回结果，但不具备严格的重排质量门控。面试展示完整质量门控时，应提前下载重排模型，改为 `ENABLE_RERANKER=true` 和 `RETRIEVAL_GATE_MODE=enforce`。

## 4. 在 PyCharm 中配置

1. 启动 PyCharm，选择 **Open**，打开 `E:\edu-rag`，不要打开整个 E 盘。
2. 打开 **File -> Settings -> Project: edu-rag -> Python Interpreter**。
3. 选择 **Add Interpreter -> Add Local Interpreter -> Virtualenv**。
4. Location 填 `E:\edu-rag\.venv`，Base interpreter 选择可用的 Python 3.11–3.13，确认创建。
5. 打开 PyCharm 下方 **Terminal**，执行 `python -m pip install -r requirements.txt`。
6. 确认项目根目录已有 `.env`。不要把 API Key 提交到 Git。
7. 打开 `main.py`，在第一个入口处右键，选择 **Run 'main'**。
8. 看到 `Uvicorn running on http://127.0.0.1:8000` 后访问 `/health`、`/docs` 和首页。

推荐另建一个运行配置：

- Name：`Private-RAG API`
- Run：Python
- Script path：`E:\edu-rag\main.py`
- Working directory：`E:\edu-rag`
- Python interpreter：`E:\edu-rag\.venv\Scripts\python.exe`
- Environment variables：保持空，让项目自动读取 `.env`

调试时，在 `core/graph.py` 的 `classify_node`、`retrieve_node`、`retrieval_gate_node` 和 `generate_node` 第一行各打一个断点，然后使用 **Debug** 启动。发出问题后，观察 `state` 中的 `complexity`、`retrieved_docs`、`retrieval_decision` 和 `answer`。

## 5. 五分钟面试演示脚本

演示前提前启动 Docker、Ollama 和 API，避免把时间浪费在下载模型上。

1. 打开 `http://127.0.0.1:8000/health`，说明后端与向量库正常。
2. 打开首页，新建“公司制度库”。
3. 上传 `sample_docs/员工手册_差旅制度.md`。
4. 提问：“员工去上海出差，住宿和交通分别按什么标准报销？”
5. 展示流式回答及文件名、页码/片段、相关性分数。
6. 再问一个文档外问题，例如“公司的年终奖是多少？”，展示低证据时的重试或拒答。
7. 在 PyCharm 中打开 `core/graph.py`，沿图解释 classify -> retrieve -> rerank -> gate -> generate/retry/abstain。
8. 打开 `core/vectorestore.py`，解释为什么同时使用向量召回和 BM25，以及为何 RRF 分数不能当成相关性阈值。
9. 打开 `core/scope.py` 和测试，解释 `knowledge_base_id` 同时约束 Milvus 与 BM25，防止跨库数据泄漏。

## 6. 面试时怎样介绍

一分钟版本：

> 这是我基于开源教育 RAG 项目二次开发的通用私有知识库系统。我把原有的学科意图路由重构为显式知识库作用域，补齐了知识库 CRUD、文档隔离和可追溯引用。检索侧使用 Milvus 稠密召回与 BM25 稀疏召回，通过 RRF 融合，再用 CrossEncoder 重排。整个流程由 LangGraph 编排，质量门控会根据重排结果决定生成、改写重试或拒答，减少无依据回答。FastAPI 提供普通和 SSE 流式接口，并用 SQLite 保存业务元数据。

一定如实说“基于开源项目二次开发”，并能指出自己具体改了什么。不要声称整个系统从零开发，也不要写没有真实测过的准确率、召回率或延迟。

可以重点讲三个工程问题：

- 数据隔离：只过滤向量召回还不够，进程内 BM25 候选也必须严格过滤 `knowledge_base_id`。
- 分数语义：向量相似度、BM25 分数、RRF 融合分数和 CrossEncoder 相关性分数不是同一种量，门控必须使用含义正确的分数。
- 幻觉控制：低质量证据不直接交给 LLM；先按原因改写查询并重试，仍不足则明确拒答。

## 7. 高频追问

**为什么不只用向量检索？** 语义检索能找到同义表达，但对产品型号、条款编号和精确关键词未必稳定；BM25 能补足这一类查询。

**为什么使用 RRF？** 两路检索原始分数的尺度不同，直接加权容易失真；RRF 基于名次融合，简单且鲁棒。

**为什么还要 CrossEncoder？** 双塔 Embedding 适合快速召回，CrossEncoder 联合阅读问题和片段，速度较慢但排序更准，所以只处理候选集。

**LangGraph 的价值是什么？** 它把重试、分支、会话状态和节点职责显式化，比一长串条件语句更易测试和扩展。

**怎样评估？** 检索侧看 Recall@K、MRR、nDCG；答案侧看忠实度、答案相关性、引用正确性；工程侧看 P50/P95 延迟、失败率和成本。必须固定测试集再比较版本。

**生产环境还缺什么？** 鉴权与租户权限、持久化任务队列、模型与索引版本管理、可观测性、限流、敏感信息处理、增量索引、备份恢复，以及系统化评测集。

## 8. 自己练习的最低标准

在投简历前，至少做到：

- 不看资料画出入库链路和问答链路；
- 能在断点中解释 `RAGState` 四个关键字段；
- 能说清 RRF 与 CrossEncoder 的区别；
- 能现场创建库、上传文件、问文档内问题和文档外问题；
- 能运行 `pytest -q test/test_private_rag.py`；
- 能如实区分上游代码与自己的改造；
- 准备一组真实评测数据与结果，而不是口头声称“效果提升”。
