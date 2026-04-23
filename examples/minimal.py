"""
Seeka Minimal Example

Zero config: only a storage path is required.
Uses local SentenceTransformer for embedding – no API keys needed.

Run:
    python examples/minimal.py
"""

import asyncio
import tempfile
from pathlib import Path
from seeka import Memory

DATA_DIR = Path(tempfile.gettempdir()) / "seeka" / "minimal"
DATA_DIR.mkdir(parents=True, exist_ok=True)

mem = Memory(str(DATA_DIR))


async def main():
    await mem.forget()

    await mem.note("I love pour-over coffee in the morning.")
    await mem.note("I started learning guitar two weeks ago.")
    print("notes recorded")

    memos = await mem.dream()
    print(f"dream() -> {len(memos)} memo(s):")
    for m in memos:
        print(f"  [{m.id[:8]}] {m.content}")

    results = await mem.recall("coffee", n=2)
    print(f"\nrecall('coffee') -> {len(results)} result(s):")
    for r in results:
        print(f"  [{r.id[:8]}] {r.content}")


if __name__ == "__main__":
    asyncio.run(main())
