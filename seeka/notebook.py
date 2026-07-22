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
                key        TEXT,
                content    TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}',
                namespace  TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'pending',
                created    INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_notes_ns_key
                ON notes(namespace, key) WHERE key IS NOT NULL;
        """)
        conn.commit()
        conn.close()

    async def add(self, note: Note) -> Note:
        """Persist a Note to the notes table. id and created are set by Note itself."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO notes (id, key, content, metadata, namespace, status, created)"
                " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (note.id, note.key, note.content, json.dumps(note.metadata),
                 note.namespace, note.created),
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
                key=row["key"],
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
                "INSERT INTO notes (id, key, content, metadata, namespace, status, created)"
                " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                [
                    (n.id, n.key, n.content, json.dumps(n.metadata), n.namespace, n.created)
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

    # ------------------------------------------------------------------
    # Key-based CRUD — for LLM-addressable working memory
    # ------------------------------------------------------------------

    async def get_by_key(self, key: str) -> Note | None:
        """Return a Note by its semantic key, or None if not found."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM notes WHERE namespace = ? AND key = ? LIMIT 1",
                (self._namespace, key),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return Note(
            id=row["id"],
            key=row["key"],
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            namespace=row["namespace"],
            status=row["status"],
            created=row["created"],
        )

    async def upsert_by_key(self, note: Note) -> Note:
        """Insert or update a Note by key. If key exists, overwrite content/metadata."""
        import json
        async with aiosqlite.connect(self._path) as conn:
            # Check if key already exists
            async with conn.execute(
                "SELECT id FROM notes WHERE namespace = ? AND key = ? LIMIT 1",
                (self._namespace, note.key),
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                # Update existing note's content and metadata, reset to pending
                await conn.execute(
                    "UPDATE notes SET content = ?, metadata = ?, status = 'pending' "
                    "WHERE namespace = ? AND key = ?",
                    (note.content, json.dumps(note.metadata), self._namespace, note.key),
                )
            else:
                # Insert new
                await conn.execute(
                    "INSERT INTO notes (id, key, content, metadata, namespace, status, created)"
                    " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (note.id, note.key, note.content, json.dumps(note.metadata),
                     note.namespace, note.created),
                )
            await conn.commit()
        return note

    async def list_keys(self) -> list[tuple[str, str]]:
        """Return (key, content_preview) for all keyed notes in this namespace."""
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute(
                "SELECT key, substr(content, 1, 80) FROM notes "
                "WHERE namespace = ? AND key IS NOT NULL ORDER BY created",
                (self._namespace,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]

    async def delete_by_key(self, key: str) -> bool:
        """Delete a note by key. Returns True if a row was deleted."""
        async with aiosqlite.connect(self._path) as conn:
            cursor = await conn.execute(
                "DELETE FROM notes WHERE namespace = ? AND key = ?",
                (self._namespace, key),
            )
            await conn.commit()
            return cursor.rowcount > 0
