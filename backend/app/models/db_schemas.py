from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_document_record(
    file_info: dict,
    title: str = "",
    category: str = "general",
    source_group: str = "user_upload",
    uploaded_by: str = "system",
    status: str = "uploaded",
    kb_version: str = "v1",
) -> dict[str, Any]:
    original_file_name = file_info.get("original_file_name", "") or file_info.get("file_name", "")
    return {
        "document_code": str(uuid4()),
        "title": title or original_file_name,
        "file_name": file_info.get("file_name", ""),
        "original_file_name": original_file_name,
        "file_path": file_info.get("file_path", ""),
        "file_type": file_info.get("file_extension", ""),
        "file_size_bytes": file_info.get("file_size_bytes", 0),
        "category": category,
        "source_group": source_group,
        "status": status,
        "uploaded_by": uploaded_by,
        "uploaded_at": utc_now_iso(),
        "processed_at": None,
        "kb_version": kb_version,
        "source_file_path": file_info.get("source_file_path", ""),
        "vector_backend": file_info.get("vector_backend", ""),
        "vector_index_path": file_info.get("vector_index_path", ""),
        "vector_collection": file_info.get("vector_collection", ""),
        "vector_status": file_info.get("vector_status", "not_indexed"),
        "embedding_model": file_info.get("embedding_model", ""),
        "synced_at": file_info.get("synced_at"),
    }


def build_chunk_record(
    document_id: str,
    chunk: dict,
    kb_version: str = "v1",
) -> dict[str, Any]:
    chunk_id = chunk.get("chunk_id", str(uuid4()))
    content = chunk.get("content", "")
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "chunk_index": chunk.get("chunk_index", 0),
        "content": content,
        "char_count": chunk.get("char_count", 0),
        "word_count": chunk.get("word_count", 0),
        "source_file_name": chunk.get("source_file_name", ""),
        "source_file_extension": chunk.get("source_file_extension", ""),
        "category": chunk.get("category", "general"),
        "source_group": chunk.get("source_group", "user_upload"),
        "kb_version": kb_version,
        "paragraph_index": chunk.get("paragraph_index", ""),
        "subchunk_index": chunk.get("subchunk_index", ""),
        "chunk_sequence": chunk.get("chunk_sequence", ""),
        "source_file_path": chunk.get("source_file_path", ""),
        "vector_backend": chunk.get("vector_backend", ""),
        "vector_index_path": chunk.get("vector_index_path", ""),
        "vector_collection": chunk.get("vector_collection", ""),
        "vector_id": chunk.get("vector_id", chunk_id),
        "vector_status": chunk.get("vector_status", "not_indexed"),
        "embedding_model": chunk.get("embedding_model", ""),
        "content_hash": chunk.get("content_hash", ""),
        "indexed_at": chunk.get("indexed_at"),
        "synced_at": chunk.get("synced_at"),
        "created_at": utc_now_iso(),
    }


def build_conversation_record(
    session_id: str,
    user_id: str = "",
    title: str = "",
    status: str = "active",
) -> dict[str, Any]:
    timestamp = utc_now_iso()

    return {
        "session_id": session_id,
        "user_id": user_id,
        "title": title or f"Conversation {session_id}",
        "status": status,
        "active_topic_id": "",
        "last_topic_anchor": "",
        "last_topic_focus": "",
        "last_topic_effective_question": "",
        "topic_history_buffer": [],
        "active_file_id": None,
        "active_file_name": "",
        "active_file_mode": "",
        "last_file_effective_question": "",
        "last_file_anchor_text": "",
        "last_file_chunk_ids": [],
        "active_file_updated_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_message_record(
    conversation_id: str,
    role: str,
    question: str = "",
    normalized_question: str = "",
    effective_question: str = "",
    answer: str = "",
    input_type: str = "text_only",
    file_id: str | None = None,
    workflow_context: str = "",
    retrieved_chunk_ids: list[str] | None = None,
    router_label: str = "",
    rewrite_applied: bool = False,
    rewrite_reason: str = "",
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "role": role,
        "question": question,
        "normalized_question": normalized_question,
        "effective_question": effective_question,
        "answer": answer,
        "input_type": input_type,
        "file_id": file_id,
        "workflow_context": workflow_context,
        "retrieved_chunk_ids": retrieved_chunk_ids or [],
        "router_label": router_label,
        "rewrite_applied": rewrite_applied,
        "rewrite_reason": rewrite_reason,
        "created_at": utc_now_iso(),
    }


def build_report_record(
    *,
    user_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
    report_type: str,
    content: str,
    client_context: dict | None = None,
    message_snapshot: dict | None = None,
    attachment: dict | None = None,
    status: str = "new",
) -> dict[str, Any]:
    timestamp = utc_now_iso()
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "report_type": report_type,
        "content": content,
        "status": status,
        "client_context": client_context or {},
        "message_snapshot": message_snapshot or {},
        "attachment": attachment or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_exact_cache_record(
    question: str,
    normalized_question: str,
    cache_key: str,
    answer: str,
    router_label: str = "",
    kb_version: str = "v1",
    source_type: str = "text_only",
) -> dict[str, Any]:
    timestamp = utc_now_iso()

    return {
        "cache_key": cache_key,
        "question": question,
        "normalized_question": normalized_question,
        "answer": answer,
        "router_label": router_label,
        "kb_version": kb_version,
        "source_type": source_type,
        "hit_count": 0,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
