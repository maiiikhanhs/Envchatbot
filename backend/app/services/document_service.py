from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.database.mongo import (
    DOCUMENT_CHUNKS_COLLECTION,
    DOCUMENTS_COLLECTION,
    get_collection,
)
from app.models.db_schemas import (
    build_chunk_record,
    build_document_record,
)


def create_document(
    file_info: dict,
    title: str = "",
    category: str = "general",
    source_group: str = "user_upload",
    uploaded_by: str = "system",
    kb_version: str = "v1",
    status: str = "uploaded",
) -> str:
    record = build_document_record(
        file_info=file_info,
        title=title,
        category=category,
        source_group=source_group,
        uploaded_by=uploaded_by,
        status=status,
        kb_version=kb_version,
    )
    result = get_collection(DOCUMENTS_COLLECTION).insert_one(record)

    return str(result.inserted_id)


def save_document_chunks(
    document_id: str,
    chunks: Iterable[dict],
    kb_version: str = "v1",
) -> int:
    records = [build_chunk_record(document_id, chunk, kb_version) for chunk in chunks]

    if not records:
        return 0

    get_collection(DOCUMENT_CHUNKS_COLLECTION).insert_many(records)

    return len(records)


def build_chunk_documents_for_storage(
    document_id: str,
    chunks: Iterable[dict],
    *,
    category: str = "general",
    source_group: str = "user_upload",
    kb_version: str = "v1",
) -> list[dict]:
    chunk_documents = []

    for chunk in chunks:
        chunk_document = dict(chunk)
        chunk_document["document_id"] = document_id
        chunk_document["category"] = category
        chunk_document["source_group"] = source_group
        chunk_document["kb_version"] = kb_version
        chunk_documents.append(chunk_document)

    return chunk_documents


def update_document_status(
    document_id: str,
    status: str,
    kb_version: str | None = None,
) -> None:
    update_payload = {
        "status": status,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    if kb_version is not None:
        update_payload["kb_version"] = kb_version

    get_collection(DOCUMENTS_COLLECTION).update_one(
        {"_id": _safe_object_id(document_id)},
        {"$set": update_payload},
    )

def get_document(document_id: str) -> dict | None:
    return get_collection(DOCUMENTS_COLLECTION).find_one(
        {"_id": _safe_object_id(document_id)}
    )


def list_document_chunks(
    document_id: str,
    kb_version: str | None = None,
) -> list[dict]:
    query = {"document_id": document_id}
    if kb_version is not None:
        query["kb_version"] = kb_version

    cursor = get_collection(DOCUMENT_CHUNKS_COLLECTION).find(query).sort("chunk_index", 1)
    return list(cursor)


def _safe_object_id(document_id: str):
    from bson import ObjectId

    return ObjectId(document_id)
