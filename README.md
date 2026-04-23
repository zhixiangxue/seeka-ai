<div align="center">

<img src="https://raw.githubusercontent.com/zhixiangxue/seeka-ai/main/docs/assets/logo.png" alt="seeka" width="120">

[![PyPI version](https://badge.fury.io/py/seeka.svg)](https://badge.fury.io/py/seeka)
[![Python Version](https://img.shields.io/pypi/pyversions/seeka)](https://pypi.org/project/seeka/)
[![License](https://img.shields.io/github/license/zhixiangxue/seeka-ai)](LICENSE)

**Embedded. Extensible. No infrastructure.**

seeka is an embedded memory component for AI Agents — like SQLite, it runs inside your process with no server, no setup, and no external dependencies. Drop it into any Agent in minutes.

Memory quality is not hardcoded. seeka's **Skills** system lets you define exactly how raw input is interpreted and extracted — for any domain, any use case — without touching the core pipeline.

</div>

---

## Core Features

### Minimalist API

No pipelines, no schemas, no boilerplate:

```python
from seeka import Memory

mem = Memory("./my_memory", llm_uri="openai/gpt-4o-mini", llm_api_key="sk-...")

# Step by step
await mem.note("User prefers dark roast coffee and dislikes anything too sweet.")
await mem.dream()   # LLM refines notes → structured Memos, embeddings stored
results = await mem.recall("coffee preference")

# Or in one call
memos = await mem.remember("User prefers dark roast coffee and dislikes anything too sweet.")
```

`note()` is instant — no network call, just persists raw text. `dream()` does the heavy lifting asynchronously when you're ready. `remember()` combines both into a single call for simple use cases. `recall()` is a semantic vector search over everything that's been dreamed.

### Automatic Conflict Resolution

When new memories contradict existing ones, seeka detects and removes the outdated entries automatically during `dream()`. No manual bookkeeping required.

```python
await mem.note("User loves coffee — has a cup every morning.")
await mem.dream()

# Later: user's situation changes
await mem.note("User was diagnosed with acid reflux and has completely stopped drinking coffee.")
await mem.dream()  # ← old coffee memo is removed automatically

results = await mem.recall("coffee")
# Returns only the new "stopped drinking coffee" memo
```

### Extraction Skills — Memory Quality You Control

Memory quality is determined by Skills, not by a fixed pipeline baked into the library. Skills are plain Markdown files that live in your project. seeka ships two built-in skills; you can write your own for any domain, any output format, any extraction rule.

**Built-in skills:**

```python
from seeka.skills import GENERAL, PREFERENCE

# GENERAL: third-person, resolves relative time refs, preserves complete facts
mem = Memory("./my_memory", ..., skills=[GENERAL])

# PREFERENCE: extracts only explicit and implicit preference signals
# Filters out events and plans — keeps attitude/taste/value judgments only
mem = Memory("./my_memory", ..., skills=[PREFERENCE])

# Combine both
mem = Memory("./my_memory", ..., skills=[GENERAL, PREFERENCE])
```

**Custom skills** — a skill is just a directory with a `SKILL.md` file:

```
my_project/
  skills/
    meeting_notes/
      SKILL.md        ← name, description, extraction rules
      guidelines.md   ← optional supporting files
```

```markdown
---
name: meeting_notes_extraction
description: Extract action items and decisions from meeting notes.
---

Your job is to extract **action items** and **decisions** only.
Ignore open questions, background context, and attendance.

Output action items as: "Owner: task by deadline"
Output decisions as: "Decision: ..."
```

```python
mem = Memory("./my_memory", ..., skills=["./skills/meeting_notes"])
```

The LLM sees only the skill's `name` and `description` initially. The full body is only revealed after the LLM decides to activate the skill — preventing token waste on irrelevant domains.

### Semantic Recall + Reranking

`recall()` embeds the query and returns the closest Memos by vector similarity. Optionally boost precision with a reranker:

```python
# Basic semantic search
results = await mem.recall("coffee preference", n=5)

# With reranking (local cross-encoder, zero config)
mem = Memory("./my_memory", ..., rerank_uri="cross-encoder/ms-marco-MiniLM-L-6-v2")

# With Cohere reranker
mem = Memory("./my_memory", ...,
    rerank_uri="cohere/rerank-english-v3.0",
    rerank_api_key="...")

# With metadata filter
results = await mem.recall("preference", filter={"user_id": {"$eq": "u42"}})
```

### Namespace Isolation

Separate memory spaces for different users, sessions, or agents — all in the same directory:

```python
alice = Memory("./shared_store", namespace="alice", ...)
bob   = Memory("./shared_store", namespace="bob",   ...)

await alice.note("Alice prefers vegetarian food.")
await bob.note("Bob loves steak.")

# No cross-contamination: each namespace is completely isolated
await alice.recall("food preference")  # returns only Alice's memo
```

---

## Quick Start

### Installation

```bash
pip install seeka
```

### Zero-config example (no API keys required)

```python
import asyncio
from seeka import Memory

# No API keys — uses local SentenceTransformer for embedding
mem = Memory("./my_memory")

async def main():
    await mem.note("I love pour-over coffee in the morning.")
    await mem.note("I started learning guitar two weeks ago.")

    memos = await mem.dream()
    for m in memos:
        print(m.content)

    results = await mem.recall("coffee")
    for r in results:
        print(r.content)

asyncio.run(main())
```

### With LLM (structured extraction + conflict resolution)

```python
mem = Memory(
    "./my_memory",
    embedding_uri="openai/text-embedding-3-small",
    embedding_api_key="sk-...",
    llm_uri="openai/gpt-4o-mini",
    llm_api_key="sk-...",
)
```

See the [`examples/`](examples/) directory for runnable demos:

| File | Covers |
|------|--------|
| [`minimal.py`](examples/minimal.py) | Zero config, no API keys, local embedding only |
| [`quickstart.py`](examples/quickstart.py) | `note → dream → recall → memos` — the core loop |
| [`conflict_resolution.py`](examples/conflict_resolution.py) | Automatic conflict detection and removal |
| [`extraction_skills.py`](examples/extraction_skills.py) | Built-in skills + writing a custom skill |

---

## API Reference

### `Memory(path, **kwargs)`

All storage is placed inside `path/` — vector store files and a `seeka.db` SQLite file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Directory for all storage files |
| `namespace` | `str` | `"default"` | Logical memory partition |
| `embedding_uri` | `str` | `None` | Embedding model URI (see [Embedding Providers](#embedding-providers)) |
| `embedding_api_key` | `str` | `None` | API key for cloud embedding |
| `llm_uri` | `str` | `None` | LLM URI for `dream()` and conflict resolution |
| `llm_api_key` | `str` | `None` | API key for LLM (required when `llm_uri` is set) |
| `rerank_uri` | `str` | `None` | Reranker URI for `recall()` (see [Reranking](#reranking)) |
| `rerank_api_key` | `str` | `None` | API key for cloud reranker |
| `skills` | `list[str]` | `None` | List of skill directory paths |

### Methods

| Method | Description |
|--------|-------------|
| `await note(content, metadata?)` | Record raw input as a Note. Fast — no network call. Returns the Note id. |
| `await dream()` | Process all pending Notes: LLM extraction → embedding → conflict resolution → store. Returns `list[Memo]`. |
| `await remember(content)` | Convenience: `note()` + `dream()` in one call. |
| `await recall(query, n=5, filter?)` | Semantic search over stored Memos. Returns `list[Memo]`. |
| `await memos(limit=100, offset=0)` | Return all Memos for the namespace, newest first. |
| `await get(id)` | Return a single Memo by id, or `None`. |
| `await update(id, content, metadata?)` | Update a Memo's content. Re-embeds and writes both stores. |
| `await delete(id)` | Delete a Memo by id. |
| `await forget()` | Wipe all Memos and pending Notes for the current namespace. |

### `Memo`

The atomic unit of memory returned by `dream()`, `recall()`, and `memos()`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | nanoid, auto-generated |
| `content` | `str` | Self-contained memory statement |
| `metadata` | `dict` | User-supplied metadata |
| `namespace` | `str` | Memory partition |
| `created` | `int` | Unix timestamp of creation |
| `modified` | `int \| None` | Unix timestamp of last update |

---

## Embedding Providers

| URI | Provider | Notes |
|-----|----------|-------|
| *(none)* | `sentence-transformers` | Local, zero config, no API key needed |
| `local/model-name` | `sentence-transformers` | Specify a custom local model |
| `openai/text-embedding-3-small` | OpenAI | Any OpenAI embedding model |
| `bailian/text-embedding-v3` | Alibaba Bailian | Native batch API |
| `provider@https://base-url/model` | Any OpenAI-compatible | Custom endpoint |

---

## LLM (for `dream()` and conflict resolution)

seeka uses [chak](https://github.com/zhixiangxue/chak-ai) for LLM calls. Any model URI supported by chak works:

| URI | Provider |
|-----|----------|
| `openai/gpt-4o-mini` | OpenAI |
| `anthropic/claude-3-5-sonnet` | Anthropic |
| `google/gemini-1.5-pro` | Google Gemini |
| `bailian/qwen-plus` | Alibaba Bailian |
| `deepseek/deepseek-chat` | DeepSeek |
| `zhipu/glm-4` | Zhipu GLM |
| `moonshot/moonshot-v1-8k` | Moonshot |
| `mistral/mistral-large` | Mistral |
| `xai/grok-beta` | xAI Grok |
| `ollama/llama3.1` | Ollama (local) |
| `vllm/custom-model` | vLLM (local) |
| `provider@https://base-url/model` | Any OpenAI-compatible endpoint |

See [chak's provider list](https://github.com/zhixiangxue/chak-ai) for the full 18+ integrations.

If `llm_uri` is not set, `dream()` skips LLM processing — each Note is stored as-is as a Memo, and conflict resolution is disabled.

---

## Reranking

Optional, improves `recall()` precision by re-scoring candidates with a cross-encoder or cloud reranker.

| URI | Provider | Notes |
|-----|----------|-------|
| *(none)* | — | Disabled; pure vector search |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local cross-encoder | Zero config, no API key |
| `cohere/rerank-english-v3.0` | Cohere | `rerank_api_key` required |
| `bailian/gte-rerank` | Alibaba Bailian | `rerank_api_key` required |

When a reranker is configured, `recall(query, n=k)` fetches `3k` candidates from the vector store, reranks them, and returns the top `k`.

---

## Extraction Skills

Skills are plain directories committed alongside your project code. The only required file is `SKILL.md`.

### SKILL.md format

```markdown
---
name: my_skill_name        # snake_case, used as the tool name
description: One-line description shown to the LLM before activation.
---

Full extraction instructions shown to the LLM after it activates the skill.
Write rules, examples, output format — anything the LLM needs.
```

The LLM receives only `name` + `description` on the first pass (like a function signature). The full body is revealed only after the LLM decides this skill is relevant. Supporting files (guidelines, examples, reference data) can be added to the same directory and read on demand by the LLM.

### Built-in skills

```python
from seeka.skills import GENERAL, PREFERENCE

# GENERAL — general-purpose memory extraction
# · Converts first-person input to third-person
# · Resolves relative time refs ("yesterday" → absolute date)
# · Disambiguates pronouns and preserves entity names
# · Best for: chat history, factual user information

# PREFERENCE — preference signal extraction
# · Extracts explicit preferences ("I hate milk tea") and implicit ones
#   (repeated behavior → inferred attitude)
# · Filters out events, plans, and neutral facts
# · Best for: personalization, recommendation, user profiling
```

### Custom skill example

See [`examples/extraction_skills.py`](examples/extraction_skills.py) for a complete walkthrough including a custom meeting-notes skill.

---

## Storage Backends

seeka supports two embedded vector store backends. Both run inside your process — no server required.

| Backend | Default | Platform | Notes |
|---------|---------|----------|-------|
| [lancedb](https://github.com/lancedb/lancedb) | yes | Windows / macOS / Linux | Recommended for all platforms |
| [seekdb](https://github.com/oceanbase/seekdb) | no | Linux only | High-performance OceanBase-based store; **not supported on Windows** |

The default is **lancedb**. To use seekdb, instantiate `SeekDB` directly from `seeka.storage`.

## Is seeka right for you?

seeka is a good fit if any of these sound like you:

- You don't want to run or maintain a memory service — seeka is a library, not a server.
- You want to customize what gets stored without touching any pipeline code — drop in a Skill and you're done.
- You need per-user or per-agent memory isolation with zero database setup.
- You want memory that self-heals — conflicting facts are resolved automatically, no bookkeeping required.
- You need to ship something in an afternoon, not a sprint.

seeka is not a good fit if you need to index large document collections (RAG), run complex structured queries, or handle bulk-write throughput at scale.

---

<div align="right"><img src="https://raw.githubusercontent.com/zhixiangxue/seeka-ai/main/docs/assets/logo.png" alt="seeka" width="120"></div>
