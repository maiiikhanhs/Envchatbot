from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

from app.config import (
    COMFYUI_EMBEDDED_PYTHON_PATH,
    COMFYUI_FAISS_EMBEDDING_MODEL,
    COMFYUI_FAISS_KB_PATH,
)
from app.database.mongo import DOCUMENT_CHUNKS_COLLECTION, DOCUMENTS_COLLECTION, get_collection

KNOWLEDGE_SOURCE_GROUP = "knowledge_base"
FAISS_BACKEND = "faiss"
LEGACY_INDEXED_STATUS = "legacy_indexed"


class KnowledgeSyncError(Exception):
    pass


_FAISS_EXPORT_SCRIPT = r"""
import json
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
index_path = Path(sys.argv[1])
pkl_path = index_path / "index.pkl"
faiss_path = index_path / "index.faiss"
if not pkl_path.exists() or not faiss_path.exists():
    raise SystemExit(f"Missing FAISS files under {index_path}")

with pkl_path.open("rb") as f:
    payload = pickle.load(f)

if not isinstance(payload, tuple) or len(payload) < 2:
    raise SystemExit("Unsupported FAISS pickle payload")

docstore, index_to_docstore_id = payload[0], payload[1]
store = getattr(docstore, "_dict", {}) or {}
ordered_ids = []
if isinstance(index_to_docstore_id, dict):
    for key in sorted(index_to_docstore_id, key=lambda value: int(value) if str(value).isdigit() else str(value)):
        ordered_ids.append(index_to_docstore_id[key])
ordered_ids.extend(doc_id for doc_id in store if doc_id not in set(ordered_ids))

items = []
metadata_keys = set()
for position, doc_id in enumerate(ordered_ids, start=1):
    doc = store.get(doc_id)
    if doc is None:
        continue
    metadata = dict(getattr(doc, "metadata", {}) or {})
    metadata_keys.update(metadata.keys())
    items.append({
        "faiss_doc_id": str(doc_id),
        "position": position,
        "content": str(getattr(doc, "page_content", "") or ""),
        "metadata": metadata,
    })

print(json.dumps({
    "status": "success",
    "index_path": str(index_path),
    "index_mtime_ns": max(pkl_path.stat().st_mtime_ns, faiss_path.stat().st_mtime_ns),
    "index_size_bytes": pkl_path.stat().st_size + faiss_path.stat().st_size,
    "doc_count": len(items),
    "metadata_keys": sorted(metadata_keys),
    "items": items,
}, ensure_ascii=False))
"""


def inspect_faiss_index(index_path: str = "") -> dict:
    exported = _export_faiss_docstore(index_path or COMFYUI_FAISS_KB_PATH)
    sources = Counter(_source_file_name(item) for item in exported["items"])
    samples = [
        {
            "faiss_doc_id": item["faiss_doc_id"],
            "source_file_name": _source_file_name(item),
            "content": item["content"][:300],
            "metadata": item["metadata"],
        }
        for item in exported["items"][:5]
    ]
    return {
        "status": "success",
        "index_path": exported["index_path"],
        "kb_version": _kb_version(exported),
        "doc_count": exported["doc_count"],
        "source_count": len(sources),
        "metadata_keys": exported["metadata_keys"],
        "sources": [{"source_file_name": name, "chunk_count": count} for name, count in sources.most_common()],
        "samples": samples,
    }


def sync_faiss_to_mongo(index_path: str = "") -> dict:
    exported = _export_faiss_docstore(index_path or COMFYUI_FAISS_KB_PATH)
    normalized_index_path = _normalize_path(exported["index_path"])
    kb_version = _kb_version(exported)
    synced_at = _utc_now()

    docs_by_source = _upsert_source_documents(exported["items"], normalized_index_path, kb_version, synced_at)
    chunks_upserted = _upsert_chunks(exported["items"], docs_by_source, normalized_index_path, kb_version, synced_at)

    return {
        "status": "success",
        "index_path": normalized_index_path,
        "kb_version": kb_version,
        "source_count": len(docs_by_source),
        "chunk_count": chunks_upserted,
        "message": "Đã đồng bộ FAISS docstore sang MongoDB.",
    }


def list_knowledge_documents(limit: int = 100, skip: int = 0) -> list[dict]:
    cursor = (
        get_collection(DOCUMENTS_COLLECTION)
        .find({"source_group": KNOWLEDGE_SOURCE_GROUP})
        .sort([("source_file_name", 1), ("title", 1)])
        .skip(max(0, int(skip)))
        .limit(max(1, min(int(limit), 500)))
    )
    documents = []
    for doc in cursor:
        item = _serialize_mongo_doc(doc)
        item["chunk_count"] = get_collection(DOCUMENT_CHUNKS_COLLECTION).count_documents(
            {"document_id": str(doc["_id"]), "source_group": KNOWLEDGE_SOURCE_GROUP}
        )
        documents.append(item)
    return documents


def list_knowledge_chunks(document_id: str, limit: int = 100, skip: int = 0) -> list[dict]:
    query = {"document_id": document_id, "source_group": KNOWLEDGE_SOURCE_GROUP}
    cursor = (
        get_collection(DOCUMENT_CHUNKS_COLLECTION)
        .find(query)
        .sort("chunk_index", 1)
        .skip(max(0, int(skip)))
        .limit(max(1, min(int(limit), 500)))
    )
    return [_serialize_mongo_doc(chunk) for chunk in cursor]


def _export_faiss_docstore(index_path: str) -> dict:
    python_path = Path(COMFYUI_EMBEDDED_PYTHON_PATH)
    resolved_index_path = Path(index_path).expanduser().resolve()
    if not python_path.exists():
        raise KnowledgeSyncError(f"Không tìm thấy Python embedded của ComfyUI: {python_path}")
    if not resolved_index_path.exists():
        raise KnowledgeSyncError(f"Không tìm thấy FAISS index path: {resolved_index_path}")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [str(python_path), "-", str(resolved_index_path)],
        input=_FAISS_EXPORT_SCRIPT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=90,
    )
    if result.returncode != 0:
        raise KnowledgeSyncError((result.stderr or result.stdout or "Không đọc được FAISS index.").strip())
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise KnowledgeSyncError(f"FAISS exporter trả JSON không hợp lệ: {exc}") from exc
    if data.get("status") != "success":
        raise KnowledgeSyncError("FAISS exporter không trả trạng thái success.")
    return data


def _upsert_source_documents(items: list[dict], index_path: str, kb_version: str, synced_at: str) -> dict[str, str]:
    grouped = defaultdict(list)
    for item in items:
        grouped[_source_path(item)].append(item)

    docs_by_source = {}
    collection = get_collection(DOCUMENTS_COLLECTION)
    for source_path, source_items in grouped.items():
        source_name = _source_file_name(source_items[0])
        document_code = f"faiss_source_{_short_hash(source_path)}"
        payload = {
            "document_code": document_code,
            "title": source_name,
            "file_name": source_name,
            "original_file_name": source_name,
            "file_path": source_path,
            "source_file_path": source_path,
            "file_type": Path(source_name).suffix,
            "file_size_bytes": 0,
            "category": "knowledge_base",
            "source_group": KNOWLEDGE_SOURCE_GROUP,
            "status": "processed",
            "uploaded_by": "comfyui_faiss_sync",
            "processed_at": synced_at,
            "kb_version": kb_version,
            "vector_backend": FAISS_BACKEND,
            "vector_index_path": index_path,
            "vector_collection": "",
            "vector_status": LEGACY_INDEXED_STATUS,
            "embedding_model": COMFYUI_FAISS_EMBEDDING_MODEL,
            "synced_at": synced_at,
            "chunk_count": len(source_items),
        }
        result = collection.update_one(
            {
                "document_code": document_code,
                "source_group": KNOWLEDGE_SOURCE_GROUP,
                "vector_backend": FAISS_BACKEND,
            },
            {"$set": payload, "$setOnInsert": {"uploaded_at": synced_at}},
            upsert=True,
        )
        if result.upserted_id:
            docs_by_source[source_path] = str(result.upserted_id)
        else:
            existing = collection.find_one(
                {
                    "document_code": document_code,
                    "source_group": KNOWLEDGE_SOURCE_GROUP,
                    "vector_backend": FAISS_BACKEND,
                },
                {"_id": 1},
            )
            docs_by_source[source_path] = str(existing["_id"])
    return docs_by_source


def _upsert_chunks(
    items: list[dict],
    docs_by_source: dict[str, str],
    index_path: str,
    kb_version: str,
    synced_at: str,
) -> int:
    collection = get_collection(DOCUMENT_CHUNKS_COLLECTION)
    index_hash = _short_hash(index_path)
    count = 0
    for item in items:
        source_path = _source_path(item)
        content = item["content"]
        metadata = item["metadata"]
        chunk_id = f"faiss_{index_hash}_{item['faiss_doc_id']}"
        payload = {
            "document_id": docs_by_source[source_path],
            "chunk_id": chunk_id,
            "chunk_index": int(metadata.get("chunk_sequence") or item["position"]),
            "content": content,
            "char_count": len(content),
            "word_count": len(content.split()),
            "source_file_name": _source_file_name(item),
            "source_file_extension": Path(_source_file_name(item)).suffix,
            "category": "knowledge_base",
            "source_group": KNOWLEDGE_SOURCE_GROUP,
            "kb_version": kb_version,
            "paragraph_index": str(metadata.get("paragraph_index", "")),
            "subchunk_index": str(metadata.get("subchunk_index", "")),
            "chunk_sequence": str(metadata.get("chunk_sequence", item["position"])),
            "source_file_path": source_path,
            "vector_backend": FAISS_BACKEND,
            "vector_index_path": index_path,
            "vector_collection": "",
            "vector_id": item["faiss_doc_id"],
            "vector_status": LEGACY_INDEXED_STATUS,
            "embedding_model": COMFYUI_FAISS_EMBEDDING_MODEL,
            "content_hash": _short_hash(content),
            "indexed_at": synced_at,
            "synced_at": synced_at,
        }
        collection.update_one(
            {"chunk_id": chunk_id},
            {"$set": payload, "$setOnInsert": {"created_at": synced_at}},
            upsert=True,
        )
        count += 1
    return count


def _source_path(item: dict) -> str:
    return _normalize_path(str(item.get("metadata", {}).get("source") or "unknown_source"))


def _source_file_name(item: dict) -> str:
    source = _source_path(item)
    return Path(source).name or "unknown_source"


def _kb_version(exported: dict) -> str:
    return f"faiss_{exported['index_mtime_ns']}"


def _normalize_path(path: str) -> str:
    return str(Path(path).expanduser().resolve()) if path and path != "unknown_source" else path


def _short_hash(text: str) -> str:
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_mongo_doc(doc: dict) -> dict:
    item = dict(doc)
    for key, value in list(item.items()):
        if isinstance(value, ObjectId):
            item[key] = str(value)
    return item
