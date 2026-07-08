"""
Seeka Quickstart — compare all three storage backends.

Runs the core memory loop (note → dream → recall) against every
StorageBackend.  Backends that are unsupported on the current platform
are skipped with a clear message rather than crashing.

On Windows you should see:
  · LANCEDB  — ✅ works
  · ZVEC     — ✅ works
  · SEEKDB   — ⚠️ skipped (pyseekdb unavailable on win32)

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
from seeka import Memory, StorageBackend

load_dotenv()
api_key = os.environ["BAILIAN_API_KEY"]

BASE_DIR = Path.home() / "seeka-data" / "quickstart"

SAMPLE_NOTES = [
    "I don't like milk tea, it's too sweet. I love pour-over coffee, especially in the morning.",
    "I started learning guitar two weeks ago. Goal: play a full song within three months.",
    "I care about value for money. I won't pay brand premiums, but I also reject low quality.",
]


def build_memory(backend: StorageBackend) -> Memory:
    """Construct a Memory instance for the given storage backend."""
    data_dir = BASE_DIR / backend.value
    data_dir.mkdir(parents=True, exist_ok=True)
    return Memory(
        str(data_dir),
        storage=backend,
        embedding_uri="bailian/text-embedding-v3",
        embedding_api_key=api_key,
        llm_uri="bailian/qwen-plus",
        llm_api_key=api_key,
    )


async def run_backend(backend: StorageBackend) -> None:
    print(f"\n{'─' * 58}")
    print(f"  Storage: {backend.name:<10}  (backend = '{backend.value}')")
    print(f"{'─' * 58}")

    # ── construct Memory (may fail on unsupported platforms) ────────
    try:
        mem = build_memory(backend)
    except RuntimeError as e:
        print(f"  ⚠️  SKIPPED — {e}")
        return

    try:
        await mem.forget()

        # ── 1. note() ───────────────────────────────────────────────
        for note_text in SAMPLE_NOTES:
            await mem.note(note_text)
        print(f"  ✅ note()  — {len(SAMPLE_NOTES)} notes recorded")

        # ── 2. dream() ──────────────────────────────────────────────
        memos = await mem.dream()
        print(f"  ✅ dream() — {len(memos)} memo(s):")
        for m in memos:
            print(f"       · {m.content}")

        # ── 3. recall() ─────────────────────────────────────────────
        results = await mem.recall("coffee preference", n=2)
        print(f"  ✅ recall('coffee preference') — {len(results)} result(s):")
        for r in results:
            print(f"       · {r.content}")

        # ── 4. memos() ─────────────────────────────────────────────
        all_memos = await mem.memos()
        print(f"  ✅ memos() — {len(all_memos)} total")

        # ── cleanup ─────────────────────────────────────────────────
        await mem.forget()

    except Exception as e:
        print(f"  ❌ Runtime error: {e}")


async def main():
    print("Seeka Quickstart — Storage Backend Comparison")
    print(f"Platform : {os.name}")
    print(f"Backends : {[b.value for b in StorageBackend]}")
    print(f"Data dir : {BASE_DIR}")

    for backend in StorageBackend:
        await run_backend(backend)

    print(f"\n{'─' * 58}")
    print("  Done.  ✅ = passed   ⚠️ = platform-unsupported (expected)")
    print(f"{'─' * 58}")


if __name__ == "__main__":
    asyncio.run(main())
