"""
Seeka Quickstart

Demonstrates the core memory loop:
  note()   – record raw input (fast, no LLM call)
  dream()  – refine pending notes into structured Memos (LLM + embedding)
  recall() – semantic search over consolidated memories

Setup:
  pip install seeka-ai
  export BAILIAN_API_KEY=sk-...   # or OPENAI_API_KEY for OpenAI models

Run:
  python examples/quickstart.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from seeka import Memory

load_dotenv()

# pyseekdb does not support NTFS-mounted paths on WSL.
# Use a native Linux home path when running inside WSL.
DATA_DIR = Path.home() / "seeka-data" / "quickstart"
DATA_DIR.mkdir(parents=True, exist_ok=True)

api_key = os.environ["BAILIAN_API_KEY"]

# Memory must be constructed before asyncio.run() to avoid signal-handler conflicts.
mem = Memory(
    str(DATA_DIR),
    embedding_uri="bailian/text-embedding-v3",
    embedding_api_key=api_key,
    llm_uri="bailian/qwen-plus",
    llm_api_key=api_key,
)


async def main():
    await mem.forget()  # start fresh for this demo

    # ── 1. Record raw notes ────────────────────────────────────────────
    # note() is lightweight: no LLM call, just persists the text.
    await mem.note("I don't like milk tea, it's too sweet. I love pour-over coffee, especially in the morning.")
    await mem.note("I started learning guitar two weeks ago. Goal: play a full song within three months.")
    await mem.note("I care about value for money. I won't pay brand premiums, but I also reject low quality.")

    print("Notes recorded.\n")

    # ── 2. Refine notes into Memos ─────────────────────────────────────
    # dream() runs the LLM to consolidate and clean up pending notes,
    # then embeds each Memo and stores it.
    memos = await mem.dream()

    print(f"dream() produced {len(memos)} memo(s):")
    for m in memos:
        print(f"  · {m.content}")
    print()

    # ── 3. Semantic recall ─────────────────────────────────────────────
    # recall() embeds the query and returns the closest Memos by vector similarity.
    results = await mem.recall("coffee preference", n=2)

    print("recall('coffee preference'):")
    for r in results:
        print(f"  → [{r.id[:8]}] {r.content}")
    print()

    # ── 4. Browse all stored Memos ─────────────────────────────────────
    all_memos = await mem.memos()
    print(f"All memos ({len(all_memos)} total):")
    for m in all_memos:
        print(f"  [{m.id[:8]}] {m.content}")


if __name__ == "__main__":
    asyncio.run(main())
