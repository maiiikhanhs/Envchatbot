from __future__ import annotations

import re
from typing import Callable

from app.services.chat_text_only_service import _compact_text
from app.services.text_with_file.context import (
    FILE_QA_BASE_TOP_K,
    FILE_QA_FOLLOW_UP_TOP_K,
    FILE_QA_MAX_CONTEXT_CHARS,
    FILE_VS_KB_MAX_CONTEXT_CHARS,
    TEXT_WITH_FILE_MODE_QA,
    TEXT_WITH_FILE_MODE_SUMMARY,
    TEXT_WITH_FILE_MODE_VS_KB,
    _build_chunk_documents_from_storage,
    _build_context_from_chunks,
    _build_file_summary_context,
    _build_file_vs_kb_context,
    _get_chunks_by_ids,
    _merge_chunks,
)
from app.services.text_with_file.resolver import (
    _classify_text_with_file_mode,
)


def _resolve_file_qa_top_k(
    question: str,
    default_top_k: int,
    *,
    prioritize_recent_chunks: bool = False,
) -> int:
    lowered = _compact_text(question).lower()
    top_k = max(default_top_k, FILE_QA_BASE_TOP_K)
    if len(lowered) >= 80 or len(re.findall(r"[0-9a-zà-ỹđ]+", lowered)) >= 8 or prioritize_recent_chunks:
        return max(top_k, FILE_QA_FOLLOW_UP_TOP_K)
    return top_k


def _process_uploaded_file(
    *,
    normalized_question: str,
    input_result: dict,
    title: str,
    category: str,
    user_id: str,
    kb_version: str,
    create_document_fn: Callable[..., str],
    chunk_file_content_fn: Callable[..., dict],
    embed_chunks_fn: Callable[[list[dict]], dict],
    build_chunk_documents_for_storage_fn: Callable[..., list[dict]],
    save_document_chunks_fn: Callable[..., int],
    upsert_chunk_embeddings_fn: Callable[[list[dict]], int],
) -> dict:
    local_file_id = create_document_fn(
        file_info=input_result["file_info"],
        title=title,
        category=category,
        uploaded_by=user_id or "system",
        kb_version=kb_version,
    )

    chunk_result = chunk_file_content_fn(
        question=normalized_question,
        file_content=input_result["file_content"],
        file_info=input_result["file_info"],
    )
    if chunk_result["status"] == "error":
        return chunk_result

    embedded_result = embed_chunks_fn(chunk_result["chunks"])
    if embedded_result["status"] == "error":
        return embedded_result

    chunk_documents = build_chunk_documents_for_storage_fn(
        document_id=local_file_id,
        chunks=embedded_result["chunks"],
        category=category,
        kb_version=kb_version,
    )
    save_document_chunks_fn(
        document_id=local_file_id,
        chunks=chunk_documents,
        kb_version=kb_version,
    )
    upsert_chunk_embeddings_fn(chunk_documents)
    return {
        "status": "success",
        "file_id": local_file_id,
        "chunk_documents": chunk_documents,
    }


def prepare_text_with_file_runtime(
    *,
    normalized_question: str,
    effective_question: str,
    input_result: dict,
    uploaded_now: bool,
    active_document: dict | None,
    active_file_id: str,
    active_file_name: str,
    active_file_source: str,
    last_file_chunk_ids: list[str],
    title: str,
    category: str,
    user_id: str,
    kb_version: str,
    top_k: int,
    create_document_fn: Callable[..., str],
    chunk_file_content_fn: Callable[..., dict],
    embed_chunks_fn: Callable[[list[dict]], dict],
    build_chunk_documents_for_storage_fn: Callable[..., list[dict]],
    save_document_chunks_fn: Callable[..., int],
    upsert_chunk_embeddings_fn: Callable[[list[dict]], int],
    list_document_chunks_fn: Callable[..., list[dict]],
    query_similar_chunks_by_question_fn: Callable[..., list[dict]],
    refine_context_fn: Callable[..., dict],
    update_document_status_fn: Callable[..., None],
) -> dict:
    text_with_file_mode = _classify_text_with_file_mode(effective_question)
    resolved_active_file_source = _compact_text(active_file_source)
    file_info = input_result.get("file_info") or {}
    resolved_active_file_name = (
        file_info.get("original_file_name")
        or file_info.get("file_name")
        or active_file_name
        or (active_document or {}).get("original_file_name", "")
        or (active_document or {}).get("file_name", "")
    )

    local_file_id = _compact_text(active_file_id)
    local_active_document = active_document
    chunk_documents: list[dict] = []

    if uploaded_now:
        uploaded_result = _process_uploaded_file(
            normalized_question=normalized_question,
            input_result=input_result,
            title=title,
            category=category,
            user_id=user_id,
            kb_version=kb_version,
            create_document_fn=create_document_fn,
            chunk_file_content_fn=chunk_file_content_fn,
            embed_chunks_fn=embed_chunks_fn,
            build_chunk_documents_for_storage_fn=build_chunk_documents_for_storage_fn,
            save_document_chunks_fn=save_document_chunks_fn,
            upsert_chunk_embeddings_fn=upsert_chunk_embeddings_fn,
        )
        if uploaded_result["status"] == "error":
            return uploaded_result
        local_file_id = uploaded_result["file_id"]
        chunk_documents = uploaded_result["chunk_documents"]
        resolved_active_file_source = "uploaded_now"
    else:
        stored_chunks = list_document_chunks_fn(local_file_id, kb_version=kb_version)
        chunk_documents = _build_chunk_documents_from_storage(
            local_active_document or {},
            stored_chunks,
            kb_version,
        )

    refined_context = ""
    retrieved_chunks: list[dict] = []

    if text_with_file_mode == TEXT_WITH_FILE_MODE_SUMMARY:
        refined_context, retrieved_chunks = _build_file_summary_context(
            question=effective_question,
            chunks=chunk_documents,
        )
    else:
        prioritized_chunks = []
        if text_with_file_mode == TEXT_WITH_FILE_MODE_QA and not uploaded_now:
            prioritized_chunks = _get_chunks_by_ids(chunk_documents, last_file_chunk_ids)

        if text_with_file_mode == TEXT_WITH_FILE_MODE_VS_KB:
            file_top_k = max(top_k, 5)
            max_context_chars = FILE_VS_KB_MAX_CONTEXT_CHARS
        else:
            file_top_k = _resolve_file_qa_top_k(
                effective_question,
                top_k,
                prioritize_recent_chunks=bool(prioritized_chunks),
            )
            max_context_chars = FILE_QA_MAX_CONTEXT_CHARS

        similarity_chunks = query_similar_chunks_by_question_fn(
            question=effective_question,
            top_k=file_top_k,
            where={"document_id": local_file_id},
        )
        retrieved_chunks = _merge_chunks(prioritized_chunks, similarity_chunks)

        if not retrieved_chunks:
            refined_context, retrieved_chunks = _build_context_from_chunks(
                question=effective_question,
                chunks=chunk_documents,
                max_context_chars=max_context_chars,
                section_title="File Context",
                source_label_prefix="FILE_SOURCE",
            )
        else:
            refined_result = refine_context_fn(
                question=effective_question,
                chunks=retrieved_chunks,
                max_context_chars=max_context_chars,
                source_label_prefix="FILE_SOURCE",
                section_title="File Context",
            )
            if refined_result["status"] == "error":
                return refined_result
            refined_context = refined_result["refined_context"]
            retrieved_chunks = refined_result["chunks"]

        if text_with_file_mode == TEXT_WITH_FILE_MODE_VS_KB:
            refined_context, retrieved_chunks = _build_file_vs_kb_context(
                question=effective_question,
                chunks=retrieved_chunks,
            )

    if uploaded_now:
        update_document_status_fn(local_file_id, status="processed", kb_version=kb_version)

    return {
        "status": "success",
        "file_id": local_file_id,
        "active_file_name": resolved_active_file_name,
        "active_file_source": resolved_active_file_source,
        "text_with_file_mode": text_with_file_mode,
        "refined_context": refined_context,
        "retrieved_chunks": retrieved_chunks,
        "active_document": local_active_document,
    }
