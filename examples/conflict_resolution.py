"""
Seeka: Automatic Conflict Resolution

When new memories contradict existing ones, seeka automatically detects
and removes the outdated entries during dream().

Scenario:
  Round 1 – user loves coffee, runs three times a week.
  Round 2 – user was diagnosed with a stomach condition and quit coffee.
  Expected – the old "loves coffee" memo is removed; "quit coffee" takes over.

Run:
  python examples/conflict_resolution.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from seeka import Memory

load_dotenv()

DATA_DIR = Path.home() / "seeka-data" / "conflict"
DATA_DIR.mkdir(parents=True, exist_ok=True)

api_key = os.environ["BAILIAN_API_KEY"]

mem = Memory(
    str(DATA_DIR),
    embedding_uri="bailian/text-embedding-v3",
    embedding_api_key=api_key,
    llm_uri="bailian/qwen-plus",
    llm_api_key=api_key,
)


async def main():
    await mem.forget()

    # ── Round 1: establish baseline memories ──────────────────────────
    await mem.note("The user loves coffee and has a cup of hand-brewed coffee every morning.")
    await mem.note("The user goes running three times a week and enjoys the routine.")

    memos = await mem.dream()
    print(f"[Round 1] Stored {len(memos)} memo(s):")
    for m in memos:
        print(f"  + {m.content}")
    print()

    # ── Round 2: introduce a contradicting memory ──────────────────────
    # The user was diagnosed with a stomach condition and stopped drinking coffee.
    # dream() will detect the conflict with Round 1's coffee memo and remove it.
    await mem.note("The user was recently diagnosed with a stomach condition. "
                   "The doctor advised quitting coffee, and the user has completely stopped.")

    memos2 = await mem.dream()
    print(f"[Round 2] Stored {len(memos2)} new memo(s):")
    for m in memos2:
        print(f"  + {m.content}")
    print()

    # ── Verify: old coffee memo should be gone ─────────────────────────
    coffee_results = await mem.recall("coffee", n=3)
    print(f"recall('coffee') → {len(coffee_results)} result(s):")
    for r in coffee_results:
        print(f"  → {r.content}")
    print()

    # Running preference should still be intact
    running_results = await mem.recall("running", n=2)
    print(f"recall('running') → {len(running_results)} result(s):")
    for r in running_results:
        print(f"  → {r.content}")
    print()

    # Full snapshot
    all_memos = await mem.memos()
    print(f"All memos after conflict resolution ({len(all_memos)} total):")
    for m in all_memos:
        print(f"  [{m.id[:8]}] {m.content}")


if __name__ == "__main__":
    asyncio.run(main())
