from __future__ import annotations

import asyncio
import json
import os

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


class ZvecDB(StorageBase):
    """
    Storage implementation backed by zvec (Alibaba in-process vector db).

    namespace maps to a zvec collection directory under path.
    zvec releases the GIL during C++ calls, so we wrap sync operations
    with asyncio.to_thread for event-loop friendliness.
    """

    def __init__(self, path: str, namespace: str):
        import zvec  # lazy import – optional at module level
        self._path = path
        self._namespace = namespace
        self._db_path = os.path.join(path, namespace)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_schema(self, dimension: int):
        """Build a zvec CollectionSchema for the given vector dimension."""
        import zvec
        return zvec.CollectionSchema(
            name=self._namespace,
            vectors=zvec.VectorSchema(
                "embedding", zvec.DataType.VECTOR_FP32, dimension
            ),
            fields=[
                zvec.FieldSchema("content", zvec.DataType.STRING, nullable=True),
                zvec.FieldSchema("metadata", zvec.DataType.STRING, nullable=True),
            ],
        )

    def _open_collection(self):
        """Open an existing collection; raise if not found."""
        import zvec
        return zvec.open(self._db_path)

    def _get_or_create_collection(self, dimension: int):
        """Open the collection if it exists, otherwise create it."""
        import zvec
        try:
            return zvec.open(self._db_path)
        except Exception:
            schema = self._build_schema(dimension)
            return zvec.create_and_open(self._db_path, schema)

    @staticmethod
    def _memo_to_doc(memo: Memo):
        """Convert a Memo to a zvec Doc for insertion/upsert."""
        import zvec
        return zvec.Doc(
            id=memo.id,
            vectors={"embedding": memo.embedding},
            fields={
                "content": memo.content,
                "metadata": json.dumps(memo.metadata or {}),
            },
        )

    @staticmethod
    def _doc_to_dict(doc) -> dict:
        """Convert a zvec query result Doc back to a dict."""
        raw_meta = doc.fields.get("metadata", "{}")
        try:
            meta = json.loads(raw_meta) if raw_meta else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return {
            "id": doc.id,
            "content": doc.fields.get("content", ""),
            "metadata": meta,
        }

    # ------------------------------------------------------------------
    # Sync private layer – all actual zvec calls live here
    # ------------------------------------------------------------------

    def _sync_add(self, memo: Memo) -> None:
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        col = self._get_or_create_collection(len(memo.embedding))
        col.insert(self._memo_to_doc(memo))

    def _sync_add_batch(self, memos: list[Memo]) -> None:
        if not memos:
            return
        if any(m.embedding is None for m in memos):
            raise ValueError("All Memos must have embedding set before add_batch")
        col = self._get_or_create_collection(len(memos[0].embedding))
        col.insert([self._memo_to_doc(m) for m in memos])

    def _sync_search(
        self, embedding: list[float], n: int, filter: dict | None
    ) -> list[dict]:
        import zvec
        try:
            col = self._open_collection()
        except Exception:
            return []
        doc_count = col.stats.doc_count
        if doc_count == 0:
            return []
        # Fetch more than n to account for post-filtering candidates
        fetch_n = min(n * 3 if filter else n, doc_count)
        results = col.query(
            queries=zvec.Query(field_name="embedding", vector=embedding),
            topk=fetch_n,
        )
        dicts = [self._doc_to_dict(r) for r in results]
        if filter:
            dicts = [d for d in dicts if _matches_filter(d["metadata"], filter)]
        return dicts[:n]

    def _sync_delete(self, id: str) -> None:
        try:
            col = self._open_collection()
        except Exception:
            return
        col.delete(id)

    def _sync_update(self, memo: Memo) -> None:
        """Replace content, embedding and metadata in one atomic upsert."""
        col = self._get_or_create_collection(len(memo.embedding))
        col.upsert(self._memo_to_doc(memo))

    def _sync_forget(self) -> None:
        import zvec
        try:
            col = zvec.open(self._db_path)
            col.destroy()
        except Exception:
            pass  # collection doesn't exist – ignore

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
        """Replace a Memo's content, embedding and metadata (atomic upsert)."""
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        await asyncio.to_thread(self._sync_update, memo)

    async def forget(self) -> None:
        await asyncio.to_thread(self._sync_forget)
