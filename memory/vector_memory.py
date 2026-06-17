"""
vector_memory.py — Jarvis Semantic Long-Term Memory (ChromaDB)
Stores facts, events, and notes as vector embeddings.
Supports semantic recall: "What did I say about my project last week?"
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
    _CHROMA = True
except ImportError:
    _CHROMA = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_DB_PATH    = _base_dir() / "memory" / "chroma_db"
_LOCK       = threading.Lock()
_client: Optional["chromadb.PersistentClient"] = None
_collection = None


def _get_collection():
    global _client, _collection
    if not _CHROMA:
        return None
    with _LOCK:
        if _collection is not None:
            return _collection
        try:
            _DB_PATH.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=str(_DB_PATH))
            ef = ONNXMiniLM_L6_V2()
            _collection = _client.get_or_create_collection(
                name="jarvis_memory",
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            print(f"[VectorMemory] Collection ready — {_collection.count()} entries")
            return _collection
        except Exception as e:
            print(f"[VectorMemory] Init error: {e}")
            return None


def store(text: str, category: str = "note", key: str = "") -> bool:
    """
    Store a memory. If `key` is given, it acts as the unique ID
    (upserts if the same key exists). Otherwise, a timestamp ID is used.
    """
    if not text.strip():
        return False
    col = _get_collection()
    if col is None:
        return False
    try:
        doc_id = f"{category}::{key}" if key else f"{category}::{datetime.now().isoformat()}"
        col.upsert(
            documents=[text.strip()],
            ids=[doc_id],
            metadatas=[{
                "category": category,
                "key":      key or doc_id,
                "date":     datetime.now().strftime("%Y-%m-%d"),
                "ts":       str(int(time.time())),
            }]
        )
        print(f"[VectorMemory] Stored [{category}] {doc_id!r}: {text[:60]}")
        return True
    except Exception as e:
        print(f"[VectorMemory] Store error: {e}")
        return False


def recall(query: str, n: int = 5, category: str = "") -> list[dict]:
    """
    Semantic search. Returns up to `n` most relevant memories.
    Optionally filter by `category`.
    Returns list of {text, category, key, date, score}.
    """
    col = _get_collection()
    if col is None or col.count() == 0:
        return []
    try:
        where = {"category": category} if category else None
        results = col.query(
            query_texts=[query],
            n_results=min(n, col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        memories = []
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances",  [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            score = round(1.0 - dist, 3)   # cosine → similarity
            if score < 0.25:               # filter out irrelevant noise
                continue
            memories.append({
                "text":     doc,
                "category": meta.get("category", ""),
                "key":      meta.get("key", ""),
                "date":     meta.get("date", ""),
                "score":    score,
            })
        return memories
    except Exception as e:
        print(f"[VectorMemory] Recall error: {e}")
        return []


def forget_key(key: str, category: str = "") -> bool:
    """Delete a specific memory by key."""
    col = _get_collection()
    if col is None:
        return False
    try:
        doc_id = f"{category}::{key}" if category else key
        col.delete(ids=[doc_id])
        print(f"[VectorMemory] Deleted {doc_id!r}")
        return True
    except Exception as e:
        print(f"[VectorMemory] Forget error: {e}")
        return False


def count() -> int:
    col = _get_collection()
    if col is None:
        return 0
    return col.count()


def sync_from_json(json_memory: dict) -> None:
    """
    Bulk-import the structured JSON memory into ChromaDB on startup.
    Only inserts entries that are not already present.
    """
    if not json_memory:
        return
    for category, items in json_memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            val = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            if val:
                text = f"{key.replace('_', ' ').title()}: {val}"
                store(text, category=category, key=key)
    print(f"[VectorMemory] Synced JSON memory -> ChromaDB ({count()} total entries)")
