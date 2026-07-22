"""Seeka Quickstart — three-layer memory in one example.

Demonstrates the full memory loop: note → dream → recall
with vector DB + graph DB working together.

Setup:
  pip install seeka-ai
  export BAILIAN_API_KEY=sk-...

Run:
  python examples/quickstart.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from seeka import Memory, VectorDB, GraphDB

load_dotenv()
api_key = os.environ["BAILIAN_API_KEY"]

DATA_DIR = Path(__file__).resolve().parent.parent / "tmp" / "quickstart"

SAMPLE_NOTES = [
    "I don't like milk tea, it's too sweet. I love pour-over coffee, especially in the morning.",
    "I started learning guitar two weeks ago. Goal: play a full song within three months.",
    "I care about value for money. I won't pay brand premiums, but I also reject low quality.",
]


async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    mem = Memory(
        str(DATA_DIR),
        vector_db=VectorDB.LANCEDB,
        graph_db=GraphDB.NEUG,
        embedding_uri="bailian/text-embedding-v3",
        embedding_api_key=api_key,
        llm_uri="bailian/qwen-plus",
        llm_api_key=api_key,
    )
    await mem.forget()

    # 1. note — write raw input
    for text in SAMPLE_NOTES:
        await mem.note(text)
    print(f"[note]  {len(SAMPLE_NOTES)} notes recorded")

    # 2. dream — extract memos (vector) + entities/triples (graph)
    memos = await mem.dream()
    print(f"[dream] {len(memos)} memos extracted")
    for m in memos:
        print(f"        · {m.content}")

    # 3. check graph
    catalog = await mem._graph.get_entity_catalog()
    predicates = await mem._graph.get_predicate_catalog()
    print(f"[graph] {len(catalog)} entities, {len(predicates)} predicates")
    for e in catalog[:5]:
        print(f"        · {e['name']} ({e['type']})")

    # 4. recall — multi-path: vector similarity + graph text2statement
    results = await mem.recall("coffee preference", n=3)
    print(f"[recall] 'coffee preference' → {len(results)} results")
    for r in results:
        src = r.metadata.get("source", "vector")
        print(f"        [{src}] {r.content[:80]}")

    await mem.forget()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
