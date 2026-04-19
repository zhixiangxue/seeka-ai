import sqlite3

import aiosqlite

from .models import Note


class Notebook:
    """
    Manages the raw input queue (notes table).
    A Note is written by the developer via note() and stays pending until dream() processes it.
    """

    def __init__(self, path: str, namespace: str):
        self._path = path
        self._namespace = namespace
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
                created     INTEGER NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    async def add(self, note: Note) -> Note:
        """Persist a Note to the notes table. id and created are set by Note itself."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO notes (id, content, metadata, namespace, status, created)"
                " VALUES (?, ?, ?, ?, 'pending', ?)",
                (note.id, note.content, json.dumps(note.metadata), note.namespace, note.created),
            )
            await conn.commit()
        return note

    async def pendings(self) -> list[Note]:
        """Return all pending Notes for the bound namespace, ordered by creation time."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM notes WHERE namespace = ? AND status = 'pending'"
                " ORDER BY created",
                (self._namespace,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            Note(
                id=row["id"],
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                namespace=row["namespace"],
                status=row["status"],
                created=row["created"],
            )
            for row in rows
        ]

    async def add_batch(self, notes: list[Note]) -> list[Note]:
        """Persist multiple Notes in a single transaction."""
        import json
        if not notes:
            return []
        async with aiosqlite.connect(self._path) as conn:
            await conn.executemany(
                "INSERT INTO notes (id, content, metadata, namespace, status, created)"
                " VALUES (?, ?, ?, ?, 'pending', ?)",
                [
                    (n.id, n.content, json.dumps(n.metadata), n.namespace, n.created)
                    for n in notes
                ],
            )
            await conn.commit()
        return notes

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

    async def forget(self) -> None:
        """Delete all notes (any status) for the bound namespace."""
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute("DELETE FROM notes WHERE namespace = ?", (self._namespace,))
            await conn.commit()
