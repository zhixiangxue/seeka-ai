# seeka 架构设计

## 目录结构

```
seeka/
├── storage/
│   ├── base.py           # StorageBase 抽象接口
│   └── seekdb.py         # SeekDB 实现（唯一实现，基于 pyseekdb）
├── embedding/
│   ├── base.py           # EmbeddingBase 抽象接口
│   ├── local.py          # 本地 sentence-transformers（默认，零配置）
│   ├── openai.py         # OpenAI Embedding API
│   └── custom.py         # 用户自定义函数包装
├── rerank/
│   ├── base.py           # RerankBase 抽象接口
│   ├── local.py          # 本地 cross-encoder 实现
│   └── custom.py         # 用户自定义函数包装
├── processor/
│   ├── base.py           # ProcessorBase 抽象接口
│   ├── agent.py          # Agent 驱动实现，持有 LLM + skills，动态编排处理流程
│   └── skills/           # skill 目录，初始为空，按需添加
└── memory.py             # 公开入口，装配所有组件，暴露 add/search/delete
```

---

## 各模块职责

### storage/

`base.py` 定义接口：

```python
class StorageBase(ABC):
    def add(self, id: str, content: str, embedding: list[float],
            namespace: str, metadata: dict) -> None: ...
    def search(self, embedding: list[float], namespace: str,
               n: int) -> list[dict]: ...
    def delete(self, id: str) -> None: ...
```

`seekdb.py` 是唯一实现，直接持有 `pyseekdb.Client`，namespace 映射到 collection name。

---

### embedding/

`base.py` 定义接口：

```python
class EmbeddingBase(ABC):
    def embed(self, text: str) -> list[float]: ...
```

`local.py` 默认实现，懒加载 `all-MiniLM-L6-v2`（384 维，约 80MB，无外部依赖）。
`openai.py` 调用 OpenAI Embedding API。
`custom.py` 包装用户传入的任意 `fn: str -> list[float]`。

---

### rerank/

`base.py` 定义接口：

```python
class RerankBase(ABC):
    def rerank(self, query: str, docs: list[str]) -> list[int]: ...
    # 返回排序后的原始索引列表
```

`local.py` 使用 cross-encoder 本地推理。
`custom.py` 包装用户传入函数。
rerank 整体是可选的，不传则跳过。

---

### processor/

`base.py` 定义接口：

```python
class ProcessorBase(ABC):
    def process(self, content: str) -> list[str]: ...
    # 输入原始内容，输出若干待存储的记忆片段
```

`agent.py` 是核心实现，持有 LLM 实例和一组 skills。初始化时自动加载 `skills/` 目录下的所有 skill，Agent 在运行时根据输入内容动态决策调用哪些 skill、以何种顺序组合，而非固定管道。skills 格式与 chak 保持一致。

`skills/` 初始为空目录，skills 格式与 chak 保持一致，Agent 通过 function calling 按需调用。

processor 整体是可选的，不传 `llm_uri` 则 add 直接存原文。

---

### memory.py（公开入口）

装配所有组件，对外只暴露三个方法：

```python
class Memory:
    def __init__(
        self,
        path: str,
        embedding_uri: str = None,      # 默认本地 sentence-transformers
        embedding_api_key: str = None,
        llm_uri: str = None,            # 默认 None（跳过 extract/rewrite）
        llm_api_key: str = None,
        rerank_uri: str = None,         # 默认 None（跳过 rerank）
        rerank_api_key: str = None,
    ): ...

    def add(self, content: str, metadata: dict = None) -> str: ...
    def search(self, query: str, n: int = 5) -> list[dict]: ...
    def delete(self, id: str) -> None: ...
```

最简用法（零配置）：

```python
from seeka import Memory
mem = Memory("./my.db")
mem.add("用户喜欢手冲咖啡")
results = mem.search("咖啡偏好")
```

带全部组件：

```python
from seeka import Memory

mem = Memory(
    "./my.db",
    embedding_uri="https://api.openai.com/v1",
    embedding_api_key="sk-...",
    llm_uri="https://api.openai.com/v1",
    llm_api_key="sk-...",
    rerank_uri="https://api.cohere.ai/v1",
    rerank_api_key="...",
)
```

---

## 数据流

add 路径：`content -> processor.process（可选，Agent + skills 动态编排）-> embedding.embed -> storage.add`

search 路径：`query -> embedding.embed -> storage.search -> reranker.rerank（可选）-> list[dict]`
