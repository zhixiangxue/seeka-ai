import json
import sqlite3
import time

import aiosqlite

from .models import Memo


class Archive:
    """
    Manages the processed Memo mirror (memos table).
    Each Memo here is a redundant copy of what lives in SeekDB, kept for structured management.
    """

    def __init__(self, path: str):
        self._path = path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._path)
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS memos (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}',
                namespace  TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    async def save(self, memo: Memo) -> None:
        """Persist a processed Memo into the archive."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO memos (id, content, metadata, namespace, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (memo.id, memo.content, json.dumps(memo.metadata), memo.namespace, int(time.time())),
            )
            await conn.commit()

    async def delete(self, memo: Memo) -> None:
        """Remove a Memo from the archive by id."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute("DELETE FROM memos WHERE id = ?", (memo.id,))
            await conn.commit()
