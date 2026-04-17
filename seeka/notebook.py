import sqlite3

import aiosqlite

from .models import Note


class Notebook:
    """
    Manages the raw input queue (notes table).
    A Note is written by the developer via note() and stays pending until dream() processes it.
    """

    def __init__(self, path: str):
        self._path = path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._path)
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS notes (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}',
                namespace  TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    async def add(self, note: Note) -> Note:
        """Persist a Note to the notes table. id and created_at are set by Note itself."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO notes (id, content, metadata, namespace, status, created_at)"
                " VALUES (?, ?, ?, ?, 'pending', ?)",
                (note.id, note.content, json.dumps(note.metadata), note.namespace, note.created_at),
            )
            await conn.commit()
        return note

    async def pendings(self, namespace: str) -> list[Note]:
        """Return all pending Notes for the given namespace, ordered by creation time."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM notes WHERE namespace = ? AND status = 'pending'"
                " ORDER BY created_at",
                (namespace,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            Note(
                id=row["id"],
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                namespace=row["namespace"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def done(self, note: Note) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "UPDATE notes SET status = 'done' WHERE id = ?", (note.id,)
            )
            await conn.commit()

    async def fail(self, note: Note) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "UPDATE notes SET status = 'failed' WHERE id = ?", (note.id,)
            )
            await conn.commit()
