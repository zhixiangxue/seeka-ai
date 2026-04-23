from __future__ import annotations

import asyncio
import json

from ..models import Memo
from .base import StorageBase


def _matches_filter(metadata: dict, f: dict) -> bool:
    """
    Evaluate a MongoDB-style filter dict against a metadata dict.
    Supported operators: $eq, $ne, $gt, $gte, $lt, $lte, $in, $and, $or.
    """
    for key, condition in f.items():
        if key == "$and":
            if not all(_matches_filter(metadata, sub) for sub in condition):
                return False
        elif key == "$or":
            if not any(_matches_filter(metadata, sub) for sub in condition):
                return False
        elif isinstance(condition, dict):
            val = metadata.get(key)
            for op, operand in condition.items():
                if op == "$eq" and val != operand:
                    return False
                elif op == "$ne" and val == operand:
                    return False
                elif op == "$gt" and not (val is not None and val > operand):
                    return False
                elif op == "$gte" and not (val is not None and val >= operand):
                    return False
                elif op == "$lt" and not (val is not None and val < operand):
                    return False
                elif op == "$lte" and not (val is not None and val <= operand):
                    return False
                elif op == "$in" and val not in operand:
                    return False
        else:
            if metadata.get(key) != condition:
                return False
    return True


class LanceDB(StorageBase):
    """
    Storage implementation backed by lancedb.
    Works on all platforms including Windows.
    namespace maps to a LanceDB table name.

    Sync lancedb calls are wrapped with asyncio.to_thread so they
    don't block the event loop.
    """

    def __init__(self, path: str, namespace: str):
        import lancedb  # lazy import – optional at module level
        self._db = lancedb.connect(path)
        self._namespace = namespace

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_schema(self, dimension: int):
        """Build a PyArrow schema for the given vector dimension."""
        import pyarrow as pa
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("metadata", pa.string()),   # JSON-serialised dict
            pa.field("vector", pa.list_(pa.float32(), dimension)),
        ])

    def _open_table(self):
        """Open an existing table; raise if not found."""
        return self._db.open_table(self._namespace)

    def _get_or_create_table(self, dimension: int):
        """Open the table if it exists, otherwise create it."""
        try:
            return self._db.open_table(self._namespace)
        except Exception:
            schema = self._build_schema(dimension)
            return self._db.create_table(self._namespace, schema=schema)

    @staticmethod
    def _memo_to_row(memo: Memo) -> dict:
        return {
            "id": memo.id,
            "content": memo.content,
            "metadata": json.dumps(memo.metadata or {}),
            "vector": memo.embedding,
        }

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        raw_meta = row.get("metadata", "{}")
        try:
            meta = json.loads(raw_meta) if raw_meta else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return {
            "id": row["id"],
            "content": row["content"],
            "metadata": meta,
        }

    # ------------------------------------------------------------------
    # Sync private layer – all actual lancedb calls live here
    # ------------------------------------------------------------------

    def _sync_add(self, memo: Memo) -> None:
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        table = self._get_or_create_table(len(memo.embedding))
        table.add([self._memo_to_row(memo)])

    def _sync_add_batch(self, memos: list[Memo]) -> None:
        if not memos:
            return
        if any(m.embedding is None for m in memos):
            raise ValueError("All Memos must have embedding set before add_batch")
        table = self._get_or_create_table(len(memos[0].embedding))
        table.add([self._memo_to_row(m) for m in memos])

    def _sync_search(
        self, embedding: list[float], n: int, filter: dict | None
    ) -> list[dict]:
        try:
            table = self._open_table()
        except Exception:
            return []
        count = table.count_rows()
        if count == 0:
            return []
        rows = table.search(embedding).limit(min(n, count)).to_list()
        results = [self._row_to_dict(r) for r in rows]
        if filter:
            results = [r for r in results if _matches_filter(r["metadata"], filter)]
        return results

    def _sync_delete(self, id: str) -> None:
        try:
            table = self._open_table()
        except Exception:
            return
        # nanoid chars are alphanumeric + _ - , safe inside SQL string literal
        table.delete(f"id = '{id}'")

    def _sync_forget(self) -> None:
        try:
            self._db.drop_table(self._namespace)
        except Exception:
            pass  # table doesn't exist – ignore

    # ------------------------------------------------------------------
    # StorageBase interface – thin async wrappers
    # ------------------------------------------------------------------

    async def add(self, memo: Memo) -> None:
        await asyncio.to_thread(self._sync_add, memo)

    async def add_batch(self, memos: list[Memo]) -> None:
        await asyncio.to_thread(self._sync_add_batch, memos)

    async def search(
        self, embedding: list[float], n: int, filter: dict | None = None
    ) -> list[dict]:
        return await asyncio.to_thread(self._sync_search, embedding, n, filter)

    async def delete(self, id: str) -> None:
        await asyncio.to_thread(self._sync_delete, id)

    async def update(self, memo: Memo) -> None:
        """Replace a Memo's content, embedding and metadata (delete + re-add)."""
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        # reuse sync primitives directly – no need to go through async round-trip
        await asyncio.to_thread(self._sync_delete, memo.id)
        await asyncio.to_thread(self._sync_add, memo)

    async def forget(self) -> None:
        await asyncio.to_thread(self._sync_forget)
