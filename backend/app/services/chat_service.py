from __future__ import annotations

import time

from app.config import (
    COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH,
    COMFYUI_WORKFLOW_PATH,
    TEXT_WITH_FILE_ANSWER_CACHE_ENABLED,
)
from app.database.mongo import ensure_mongo_indexes
from app.input.input_processor import prepare_chatbot_input
from app.preprocessing.chunking import chunk_file_content
from app.retrieval.embedding import embed_chunks
from app.services.chat_text_only_service import (
    GREETING_ANSWER,
    TEXT_ONLY_CACHE_POLICY_VERSION,
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
    UNRELATED_ANSWER,
    VALID_ROUTER_LABELS,
    _build_follow_up_state,
    _build_text_only_cache_kb_version,
    _compact_text,
    _extract_reference,
    _is_follow_up_question,
    _should_cache_text_only_answer,
    build_text_only_topic_update,
    handle_text_only_request as _handle_text_only_request_impl,
)
from app.services.chat_text_with_file_service import (
    FILE_QA_BASE_TOP_K,
    FILE_QA_FOLLOW_UP_TOP_K,
    FILE_QA_MAX_CONTEXT_CHARS,
    FILE_SUMMARY_MAX_CONTEXT_CHARS,
    FILE_VS_KB_MAX_CONTEXT_CHARS,
    TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK,
    TEXT_WITH_FILE_MODE_QA,
    TEXT_WITH_FILE_MODE_SUMMARY,
    TEXT_WITH_FILE_MODE_VS_KB,
    VALID_TEXT_WITH_FILE_ROUTER_LABELS,
    _build_file_anchor_text,
    _build_file_summary_context,
    _classify_text_with_file_mode,
    _normalize_chunk_ids,
    _resolve_file_qa_top_k,
    handle_text_with_file_request as _handle_text_with_file_request_impl,
    prepare_text_with_file_runtime as _prepare_text_with_file_runtime_impl,
    should_retry_as_text_with_file as _should_retry_as_text_with_file_impl,
)
from app.services.chat_runtime.answer_policy import (
    finalize_comfyui_response as _finalize_comfyui_response,
    is_unusable_text_with_file_answer as _is_unusable_text_with_file_answer,
    sanitize_final_response as _sanitize_final_response,
    should_cache_text_with_file_answer as _should_cache_text_with_file_answer,
)
from app.services.chat_runtime.latency import (
    elapsed_ms as _elapsed_ms,
    log_chat_latency as _log_chat_latency,
)
from app.services.chat_runtime.request_flow import (
    ChatRequestState,
    activate_file_input as _activate_file_input,
    build_chat_response as _build_chat_response,
    handle_text_only_cached_response as _handle_text_only_cached_response,
    lookup_text_with_file_cached_response as _lookup_text_with_file_cached_response_impl,
    store_text_with_file_cache as _store_text_with_file_cache,
    try_resolve_active_file_request as _try_resolve_active_file_request,
)
from app.services.chat_runtime.workflow_recovery import (
    preview_workflow_result as _preview_workflow_result,
    recover_text_with_file_history_answer as _recover_text_with_file_history_answer,
    retry_text_with_file_workflow_once as _retry_text_with_file_workflow_once,
)
from app.services.comfyui_service import run_comfyui_workflow
from app.services.conversation_service import (
    add_assistant_message,
    add_user_message,
    find_cached_answer,
    find_cached_answer_by_cache_key,
    get_conversation_active_file_state,
    get_conversation_topic_state,
    get_or_create_conversation,
    list_file_messages,
    list_recent_messages,
    store_cached_answer,
    update_conversation_active_file_state,
    update_conversation_topic_state,
)
from app.services.semantic_answer_cache import (
    lookup_semantic_cached_answer,
    upsert_semantic_answer_cache,
)
from app.services.document_service import (
    build_chunk_documents_for_storage,
    create_document,
    get_document,
    list_document_chunks,
    save_document_chunks,
    update_document_status,
)
from app.services.vector_service import query_similar_chunks_by_question, upsert_chunk_embeddings
from app.workflow.context_refiner import refine_context

COMFYUI_TEXT_ONLY_WORKFLOW_PATH = COMFYUI_WORKFLOW_PATH

def _resolve_workflow_path_for_input_type(input_type: str) -> str | None:
    if input_type == "text_with_file":
        return COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH
    return None


def _run_workflow_for_request(
    *,
    input_type: str,
    question: str,
    context: str,
    follow_up_state: str,
    question_source_index: int,
) -> tuple[dict, dict]:
    workflow_input = {
        "question": question,
        "context": context,
        "follow_up_state": follow_up_state,
        "question_source_index": question_source_index,
    }
    workflow_path = _resolve_workflow_path_for_input_type(input_type)
    comfyui_kwargs = {
        "question": workflow_input["question"],
        "context": context,
        "question_source_index": question_source_index,
    }
    if workflow_path:
        comfyui_kwargs["workflow_path"] = workflow_path
    workflow_result = run_comfyui_workflow(**comfyui_kwargs)
    return workflow_input, workflow_result


def _prepare_text_with_file_runtime(**kwargs) -> dict:
    return _prepare_text_with_file_runtime_impl(
        **kwargs,
        create_document_fn=create_document,
        chunk_file_content_fn=chunk_file_content,
        embed_chunks_fn=embed_chunks,
        build_chunk_documents_for_storage_fn=build_chunk_documents_for_storage,
        save_document_chunks_fn=save_document_chunks,
        upsert_chunk_embeddings_fn=upsert_chunk_embeddings,
        list_document_chunks_fn=list_document_chunks,
        query_similar_chunks_by_question_fn=query_similar_chunks_by_question,
        refine_context_fn=refine_context,
        update_document_status_fn=update_document_status,
    )


def _handle_text_only_request(**kwargs) -> dict:
    return _handle_text_only_request_impl(
        **kwargs,
        run_workflow_fn=_run_workflow_for_request,
        find_cached_answer_fn=find_cached_answer,
        add_user_message_fn=add_user_message,
        add_assistant_message_fn=add_assistant_message,
        lookup_semantic_cached_answer_fn=lambda **semantic_kwargs: lookup_semantic_cached_answer(
            **semantic_kwargs,
            find_cached_answer_by_cache_key_fn=find_cached_answer_by_cache_key,
        ),
    )


def _handle_text_with_file_request(**kwargs) -> dict:
    return _handle_text_with_file_request_impl(
        **kwargs,
        prepare_runtime_fn=_prepare_text_with_file_runtime,
        run_workflow_fn=_run_workflow_for_request,
        lookup_cached_response_fn=_lookup_text_with_file_cached_response,
    )


def _lookup_text_with_file_cached_response(**kwargs) -> dict | None:
    return _lookup_text_with_file_cached_response_impl(
        **kwargs,
        find_cached_answer_by_cache_key_fn=find_cached_answer_by_cache_key,
    )


def _should_retry_as_text_with_file(**kwargs) -> bool:
    return _should_retry_as_text_with_file_impl(
        **kwargs,
        list_document_chunks_fn=list_document_chunks,
    )


def _run_text_with_file_request(**kwargs) -> dict:
    normalized_question = kwargs["normalized_question"]
    return _handle_text_with_file_request(
        **kwargs,
        effective_question=normalized_question,
    )


def process_chat_request(
    question: str,
    file_path: str | None = None,
    *,
    original_filename: str = "",
    session_id: str = "default_session",
    user_id: str = "",
    title: str = "",
    category: str = "general",
    kb_version: str = "v3_structured_policy",
    top_k: int = 3,
) -> dict:
    total_started_at = time.perf_counter()
    timings: dict[str, int] = {}

    phase_started_at = time.perf_counter()
    ensure_mongo_indexes()

    uploaded_now = bool(file_path)
    input_result = prepare_chatbot_input(question, file_path)
    timings["prepare_input"] = _elapsed_ms(phase_started_at)
    if input_result["status"] == "error":
        timings["total"] = _elapsed_ms(total_started_at)
        _log_chat_latency(timings, input_type="invalid", status="error")
        return input_result

    if uploaded_now and original_filename and input_result.get("file_info"):
        input_result["file_info"]["original_file_name"] = original_filename
        input_result["file_info"]["file_name"] = original_filename

    normalized_question = input_result["normalized_question"]
    conversation_id = get_or_create_conversation(
        session_id=session_id,
        user_id=user_id,
        title=title or normalized_question[:80],
    )
    recent_messages = list_recent_messages(conversation_id, limit=6)
    text_only_cache_kb_version = _build_text_only_cache_kb_version(kb_version)
    topic_state = get_conversation_topic_state(conversation_id)
    active_file_state = get_conversation_active_file_state(conversation_id)
    active_file_id = _compact_text(active_file_state.get("active_file_id", ""))
    active_file_name = _compact_text(active_file_state.get("active_file_name", ""))
    last_file_effective_question = _compact_text(
        active_file_state.get("last_file_effective_question", "")
    )
    last_file_chunk_ids = _normalize_chunk_ids(
        active_file_state.get("last_file_chunk_ids", [])
    )
    last_file_anchor_text = _compact_text(
        active_file_state.get("last_file_anchor_text", "")
    )
    state = ChatRequestState(
        question=question,
        normalized_question=normalized_question,
        conversation_id=conversation_id,
        input_result=input_result,
        recent_messages=recent_messages,
        topic_state=topic_state,
        active_file_state=active_file_state,
        text_only_cache_kb_version=text_only_cache_kb_version,
        uploaded_now=uploaded_now,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        last_file_effective_question=last_file_effective_question,
        last_file_chunk_ids=last_file_chunk_ids,
        last_file_anchor_text=last_file_anchor_text,
    )
    timings["state"] = _elapsed_ms(phase_started_at) - timings["prepare_input"]

    if state.input_result["input_type"] == "text_only" and not state.uploaded_now:
        phase_started_at = time.perf_counter()
        _try_resolve_active_file_request(
            state=state,
            kb_version=kb_version,
            list_file_messages_fn=list_file_messages,
            get_document_fn=get_document,
            list_document_chunks_fn=list_document_chunks,
        )
        timings["active_file_resolve"] = _elapsed_ms(phase_started_at)

    if state.input_result["input_type"] == "text_only":
        phase_started_at = time.perf_counter()
        request_state = _handle_text_only_request(
            conversation_id=state.conversation_id,
            question=state.question,
            normalized_question=state.normalized_question,
            recent_messages=state.recent_messages,
            topic_state=state.topic_state,
            text_only_cache_kb_version=state.text_only_cache_kb_version,
        )
        timings["request"] = _elapsed_ms(phase_started_at)
        if request_state["status"] == "cached":
            return _handle_text_only_cached_response(
                state=state,
                request_state=request_state,
                timings=timings,
                total_started_at=total_started_at,
                elapsed_ms_fn=_elapsed_ms,
                log_chat_latency_fn=_log_chat_latency,
                list_recent_messages_fn=list_recent_messages,
                update_conversation_topic_state_fn=update_conversation_topic_state,
            )
    else:
        phase_started_at = time.perf_counter()
        request_state = _run_text_with_file_request(
            normalized_question=state.normalized_question,
            input_result=state.input_result,
            uploaded_now=state.uploaded_now,
            active_document=state.active_document,
            active_file_id=state.active_file_id,
            active_file_name=state.active_file_name,
            active_file_source=state.active_file_source,
            active_file_reused=state.active_file_reused,
            last_file_chunk_ids=state.last_file_chunk_ids,
            recent_messages=state.recent_messages,
            title=title,
            category=category,
            user_id=user_id,
            kb_version=kb_version,
            top_k=top_k,
        )
        timings["request"] = _elapsed_ms(phase_started_at)
        if request_state["status"] == "error":
            timings["total"] = _elapsed_ms(total_started_at)
            _log_chat_latency(timings, input_type="text_with_file", status="error")
            return request_state
    state.apply_request_state(request_state)

    if (
        state.request_state["input_type"] == "text_only"
        and state.comfyui_result["status"] == "success"
    ):
        preview_answer, _, _ = _preview_workflow_result(
            input_type="text_only",
            comfyui_result=state.comfyui_result,
            retrieved_chunks=state.retrieved_chunks,
        )
        if _should_retry_as_text_with_file(
            question=state.normalized_question,
            final_answer=preview_answer,
            active_file_state=state.active_file_state,
            recent_messages=state.recent_messages,
        ):
            retry_active_file_id = _compact_text(
                state.active_file_state.get("active_file_id", "")
            )
            retry_document = get_document(retry_active_file_id)
            if retry_document is not None:
                retry_active_file_id, retry_active_file_name = _activate_file_input(
                    state.input_result,
                    retry_document,
                )
                request_state = _run_text_with_file_request(
                    normalized_question=state.normalized_question,
                    input_result=state.input_result,
                    uploaded_now=False,
                    active_document=retry_document,
                    active_file_id=retry_active_file_id,
                    active_file_name=retry_active_file_name,
                    active_file_source="active",
                    active_file_reused=True,
                    last_file_chunk_ids=state.last_file_chunk_ids,
                    recent_messages=state.recent_messages,
                    title=title,
                    category=category,
                    user_id=user_id,
                    kb_version=kb_version,
                    top_k=top_k,
                )
                if request_state["status"] == "error":
                    return request_state
                state.apply_request_state(request_state)

    phase_started_at = time.perf_counter()
    state.apply_request_state(
        _retry_text_with_file_workflow_once(
            state.request_state,
            run_workflow_fn=_run_workflow_for_request,
        )
    )
    timings["retry"] = _elapsed_ms(phase_started_at)

    phase_started_at = time.perf_counter()
    add_user_message(
        conversation_id=state.conversation_id,
        question=state.question,
        normalized_question=state.normalized_question,
        effective_question=state.effective_question,
        input_type=state.request_state["input_type"],
        file_id=state.file_id,
        workflow_context=state.refined_context,
        rewrite_applied=state.rewrite_applied,
        rewrite_reason=state.rewrite_reason,
    )

    if state.comfyui_result["status"] == "success":
        final_router_label = _compact_text(state.comfyui_result.get("router_output", ""))
        state.router_output = final_router_label
        raw_workflow_answer = state.comfyui_result.get("final_output", "")
        if state.request_state["input_type"] == "text_with_file" and _is_unusable_text_with_file_answer(
            raw_workflow_answer
        ):
            recovered_answer = _recover_text_with_file_history_answer(state.comfyui_result)
            if recovered_answer:
                raw_workflow_answer = recovered_answer
        final_answer, final_retrieved_chunks = _finalize_comfyui_response(
            router_output=final_router_label,
            raw_answer=raw_workflow_answer,
            retrieved_chunks=state.retrieved_chunks,
        )
        final_answer, final_router_label, final_retrieved_chunks = _sanitize_final_response(
            input_type=state.request_state["input_type"],
            router_output=final_router_label,
            final_answer=final_answer,
            retrieved_chunks=final_retrieved_chunks,
        )
        state.comfyui_result["final_output"] = final_answer
        state.comfyui_result["router_output"] = final_router_label
        state.router_output = final_router_label
        state.retrieved_chunks = final_retrieved_chunks
        add_assistant_message(
            conversation_id=state.conversation_id,
            answer=final_answer,
            workflow_context=state.refined_context,
            retrieved_chunk_ids=[chunk["chunk_id"] for chunk in state.retrieved_chunks],
            router_label=final_router_label,
        )
        if state.request_state["input_type"] == "text_only" and _should_cache_text_only_answer(
            normalized_question=state.normalized_question,
            final_answer=final_answer,
            router_label=final_router_label,
            rewrite_applied=state.rewrite_applied,
        ):
            cache_key = store_cached_answer(
                question=state.effective_question,
                normalized_question=state.effective_question,
                answer=final_answer,
                router_label=final_router_label,
                kb_version=state.text_only_cache_kb_version,
                source_type="text_only",
            )
            upsert_semantic_answer_cache(
                cache_key=cache_key,
                question=state.effective_question,
                router_label=final_router_label,
                kb_version=state.text_only_cache_kb_version,
            )
        _store_text_with_file_cache(
            state=state,
            final_answer=final_answer,
            final_router_label=final_router_label,
            kb_version=kb_version,
            store_cached_answer_fn=store_cached_answer,
        )
        if state.request_state["input_type"] == "text_only":
            refreshed_recent_messages = list_recent_messages(state.conversation_id, limit=3)
            topic_update = build_text_only_topic_update(
                previous_topic_state=state.topic_state,
                recent_messages=refreshed_recent_messages,
                effective_question=state.effective_question,
                final_answer=final_answer,
                router_label=final_router_label,
            )
            update_conversation_topic_state(
                state.conversation_id,
                active_topic_id=topic_update["active_topic_id"],
                last_topic_anchor=topic_update["last_topic_anchor"],
                last_topic_focus=topic_update["last_topic_focus"],
                last_topic_effective_question=topic_update["last_topic_effective_question"],
                topic_history_buffer=topic_update["topic_history_buffer"],
            )
        elif state.file_id:
            anchor_answer = (
                ""
                if final_answer == TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK
                else final_answer
            )
            updated_anchor_text = _build_file_anchor_text(
                effective_question=state.effective_question
                or state.last_file_effective_question,
                final_answer=anchor_answer,
                retrieved_chunks=state.retrieved_chunks,
            )
            update_conversation_active_file_state(
                state.conversation_id,
                active_file_id=str(state.file_id),
                active_file_name=str(state.active_file_name),
                active_file_mode=state.text_with_file_mode,
                last_file_effective_question=state.effective_question
                or state.last_file_effective_question,
                last_file_chunk_ids=[
                    chunk.get("chunk_id", "") for chunk in state.retrieved_chunks
                ],
                last_file_anchor_text=updated_anchor_text or state.last_file_anchor_text,
            )
    timings["finalize"] = _elapsed_ms(phase_started_at)
    timings["total"] = _elapsed_ms(total_started_at)
    _log_chat_latency(
        timings,
        input_type=state.request_state["input_type"],
        status="success",
        router=state.router_output,
        cached=bool((state.comfyui_result or {}).get("cached")),
    )

    return _build_chat_response(state=state)
