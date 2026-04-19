"""
Seeka: Extraction Skills

Skills let you control exactly how dream() interprets and extracts memories.
A skill is a directory containing a SKILL.md file that instructs the LLM.

Seeka ships two built-in skills:
  seeka.skills.GENERAL    – third-person, resolved time refs, complete facts
  seeka.skills.PREFERENCE – preference signals only (explicit + implicit)

But the real power is writing your own skill for your domain.
Any directory with a valid SKILL.md works — see Part 3 below.

Run:
  python examples/extraction_skills.py
"""

import asyncio
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from seeka import Memory
from seeka.skills import GENERAL, PREFERENCE

load_dotenv()

DATA_DIR = Path.home() / "seeka-data" / "skills"
DATA_DIR.mkdir(parents=True, exist_ok=True)

api_key = os.environ["BAILIAN_API_KEY"]

# ── Input notes used across all three examples ─────────────────────────────
# A mix of events, preference signals, and meeting-style action items.
NOTES = [
    "Yesterday I met my old friend Lisa. We had coffee together in Sanlitun, Beijing for three hours.",
    "I don't really like milk tea — too sweet. But I love pour-over coffee, especially in the morning.",
    "Next Friday I'm heading to Shanghai for a business trip, about three days. "
    "I want to try some Benbang cuisine.",
    "I've been learning guitar for two weeks. My goal is to play a complete song within three months.",
    "I care a lot about value for money. I won't pay for brand premiums, but I also refuse poor quality.",
]

MEETING_NOTES = [
    "Weekly sync — April 19. Attendees: Alice, Bob, Carol.",
    "Bob will finish the API design doc by Wednesday.",
    "We decided to drop support for Python 3.9 starting next release.",
    "Carol needs to check with the legal team about the new data retention policy.",
    "Alice: schedule a follow-up with the infra team before end of month.",
    "Open question: should we migrate the database? No decision yet.",
]

SEP = "─" * 60


def _make_memory(subdir: str, skill: str | None = None) -> Memory:
    skills = [skill] if skill else None
    return Memory(
        str(DATA_DIR / subdir),
        embedding_uri="bailian/text-embedding-v3",
        embedding_api_key=api_key,
        llm_uri="bailian/qwen-plus",
        llm_api_key=api_key,
        skills=skills,
    )


async def run(label: str, mem: Memory, notes: list[str]) -> None:
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    await mem.forget()
    for n in notes:
        await mem.note(n)
    memos = await mem.dream()
    print(f"  {len(memos)} memo(s) extracted:")
    for i, m in enumerate(memos, 1):
        print(f"  [{i:02d}] {m.content}")


# ── Part 3: Custom skill ────────────────────────────────────────────────────
#
# A skill is just a directory with a SKILL.md file.
# SKILL.md format:
#
#   ---
#   name: <tool name, snake_case>
#   description: <one-line description shown to the LLM as a tool>
#   ---
#
#   <body: detailed instructions shown to the LLM after it activates the skill>
#
# The LLM sees only the name + description initially (like a function signature).
# When it decides to use the skill, it receives the full body as context.
# This lets you ship arbitrarily detailed instructions without polluting the
# system prompt.
#
# Below we define a "meeting notes" skill that extracts action items and
# decisions — something neither GENERAL nor PREFERENCE is designed for.

CUSTOM_SKILL_MD = """\
---
name: meeting_notes_extraction
description: Extract action items and decisions from meeting notes. Ignore discussion context; focus only on commitments and resolved decisions.
---

Your job is to extract **action items** and **decisions** from meeting notes.

## What to extract

**Action items** — a commitment to do something:
- Known owner: "Bob will send the report by Wednesday"
- Unknown owner: "Someone needs to follow up with legal"

**Decisions** — something the group resolved:
- "We decided to drop Python 3.9 support"
- "The team agreed to use PostgreSQL"

## What NOT to extract

- Open questions without a resolution → skip
- Discussion points or background context → skip
- Attendance / logistics → skip

## Output format

- Action items: start with the owner's name if known, e.g. "Bob: send API doc by Wednesday"
  If owner unknown, start with "TODO: ..."
- Decisions: start with "Decision: ...", e.g. "Decision: drop Python 3.9 support from next release"
"""


async def main():
    # ── Part 1: Built-in GENERAL skill ─────────────────────────────────
    mem_general = _make_memory("general", GENERAL)
    await run(
        "Part 1 · GENERAL skill — facts & events, resolved time references",
        mem_general,
        NOTES,
    )

    # ── Part 2: Built-in PREFERENCE skill ──────────────────────────────
    mem_preference = _make_memory("preference", PREFERENCE)
    await run(
        "Part 2 · PREFERENCE skill — attitude & taste signals only",
        mem_preference,
        NOTES,
    )

    # ── Part 3: Custom skill ────────────────────────────────────────────
    # Create a temporary skill directory at runtime.
    # In a real project, commit this directory alongside your code and pass
    # the absolute path: Memory(..., skills=["/path/to/my_skill"])
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "meeting_notes_extraction"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(CUSTOM_SKILL_MD, encoding="utf-8")

        mem_custom = _make_memory("custom", str(skill_dir))
        await run(
            "Part 3 · Custom skill — action items & decisions from meeting notes",
            mem_custom,
            MEETING_NOTES,
        )

    print(f"\n{SEP}")
    print("  Skills are plain directories — commit them with your project:")
    print("    my_project/")
    print("      skills/")
    print("        meeting_notes/")
    print("          SKILL.md          ← name, description, extraction rules")
    print("          guidelines.md     ← optional supporting files (Layer 3)")
    print()
    print("    Memory(..., skills=['./skills/meeting_notes'])")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
