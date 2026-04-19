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

    def __init__(self, path: str, namespace: str):
        self._path = path
        self._namespace = namespace
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
                created    INTEGER NOT NULL,
                modified   INTEGER
            );
        """)
        # Migrate existing databases that lack the modified column
        try:
            conn.execute("ALTER TABLE memos ADD COLUMN modified INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.close()

    async def save(self, memo: Memo) -> None:
        """Persist a processed Memo into the archive."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO memos (id, content, metadata, namespace, created, modified)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (memo.id, memo.content, json.dumps(memo.metadata), memo.namespace, memo.created, memo.modified),
            )
            await conn.commit()

    async def save_batch(self, memos: list[Memo]) -> None:
        """Persist multiple Memos in a single transaction."""
        if not memos:
            return
        async with aiosqlite.connect(self._path) as conn:
            await conn.executemany(
                "INSERT OR REPLACE INTO memos (id, content, metadata, namespace, created, modified)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (m.id, m.content, json.dumps(m.metadata), m.namespace, m.created, m.modified)
                    for m in memos
                ],
            )
            await conn.commit()

    async def get(self, id: str) -> Memo | None:
        """Return a single Memo by id, or None if not found."""
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT id, content, metadata, namespace, created, modified FROM memos"
                " WHERE id = ? AND namespace = ?",
                (id, self._namespace),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return Memo(
            id=row["id"],
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            namespace=row["namespace"],
            created=row["created"],
            modified=row["modified"],
        )

    async def update(self, id: str, content: str, metadata: dict) -> None:
        """Overwrite content and metadata, and stamp modified = now."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "UPDATE memos SET content = ?, metadata = ?, modified = ? WHERE id = ? AND namespace = ?",
                (content, json.dumps(metadata), int(time.time()), id, self._namespace),
            )
            await conn.commit()

    async def delete(self, id: str) -> None:
        """Remove a Memo from the archive by id."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute("DELETE FROM memos WHERE id = ?", (id,))
            await conn.commit()

    async def memos(self, limit: int = 100, offset: int = 0) -> list[Memo]:
        """Return all Memos for the namespace, ordered by creation time (newest first)."""
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT id, content, metadata, namespace, created, modified FROM memos"
                " WHERE namespace = ? ORDER BY created DESC LIMIT ? OFFSET ?",
                (self._namespace, limit, offset),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            Memo(
                id=r["id"],
                content=r["content"],
                metadata=json.loads(r["metadata"]),
                namespace=r["namespace"],
                created=r["created"],
                modified=r["modified"],
            )
            for r in rows
        ]

    async def forget(self) -> None:
        """Delete all Memos for the bound namespace."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute("DELETE FROM memos WHERE namespace = ?", (self._namespace,))
            await conn.commit()
