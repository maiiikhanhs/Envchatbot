from __future__ import annotations

from typing import Callable

from app.services.chat_text_only_service import _build_follow_up_state
from app.services.text_with_file.context import (
    FILE_QA_BASE_TOP_K,
    FILE_QA_FOLLOW_UP_TOP_K,
    FILE_QA_MAX_CONTEXT_CHARS,
    FILE_SUMMARY_MAX_CONTEXT_CHARS,
    FILE_VS_KB_MAX_CONTEXT_CHARS,
    TEXT_WITH_FILE_MODE_QA,
    TEXT_WITH_FILE_MODE_SUMMARY,
    TEXT_WITH_FILE_MODE_VS_KB,
    _build_file_anchor_text,
    _build_file_summary_context,
    _normalize_chunk_ids,
)
from app.services.text_with_file.assessment import build_file_vs_kb_workflow_question
from app.services.text_with_file.resolver import (
    TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK,
    VALID_TEXT_WITH_FILE_ROUTER_LABELS,
    _build_file_info_from_document,
    _classify_text_with_file_mode,
    resolve_active_conversation_file,
    should_retry_as_text_with_file,
    should_route_to_text_with_file,
)
from app.services.text_with_file.runtime import (
    _resolve_file_qa_top_k,
    prepare_text_with_file_runtime,
)


def _extract_workflow_history_preview(value, *, limit: int = 600) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        text = "\n".join(_extract_workflow_history_preview(item, limit=limit) for item in value if item is not None)
    elif isinstance(value, dict):
        if "text" in value:
            text = _extract_workflow_history_preview(value.get("text"), limit=limit)
        else:
            text = "\n".join(
                _extract_workflow_history_preview(item, limit=limit)
                for item in value.values()
                if item is not None
            )
    else:
        text = "" if value is None else str(value)
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()[:limit]


def _log_file_vs_kb_workflow_result(
    *,
    mode: str,
    file_name: str,
    workflow_question: str,
    comfyui_result: dict,
) -> None:
    outputs = ((comfyui_result.get("history") or {}).get("outputs") or {})
    print(
        "[TEXT_WITH_FILE][FILE_VS_KB] "
        f"mode={mode} file={file_name} status={comfyui_result.get('status')} "
        f"router={comfyui_result.get('router_output', '')!r} "
        f"question={workflow_question[:1000]!r}"
    )
    for node_id in ("22", "7", "13", "31", "39"):
        preview = _extract_workflow_history_preview(outputs.get(node_id))
        if preview:
            print(f"[TEXT_WITH_FILE][FILE_VS_KB][node {node_id}] {preview!r}")
    final_preview = _extract_workflow_history_preview(comfyui_result.get("final_output", ""))
    if final_preview:
        print(f"[TEXT_WITH_FILE][FILE_VS_KB][final] {final_preview!r}")


def handle_text_with_file_request(
    *,
    normalized_question: str,
    effective_question: str,
    input_result: dict,
    uploaded_now: bool,
    active_document: dict | None,
    active_file_id: str,
    active_file_name: str,
    active_file_source: str,
    active_file_reused: bool,
    last_file_chunk_ids: list[str],
    recent_messages: list[dict],
    title: str,
    category: str,
    user_id: str,
    kb_version: str,
    top_k: int,
    prepare_runtime_fn: Callable[..., dict],
    run_workflow_fn: Callable[..., tuple[dict, dict]],
    lookup_cached_response_fn: Callable[..., dict | None] | None = None,
) -> dict:
    file_info = input_result.get("file_info") or {}
    runtime_file_name = (
        file_info.get("original_file_name")
        or file_info.get("file_name")
        or (active_document or {}).get("original_file_name", "")
        or (active_document or {}).get("file_name", "")
    )
    initial_follow_up_state = _build_follow_up_state(
        recent_messages=recent_messages,
        active_file_name=str(runtime_file_name),
        active_file_id=str(active_file_id or ""),
    )

    prepared_runtime = prepare_runtime_fn(
        normalized_question=normalized_question,
        effective_question=effective_question,
        input_result=input_result,
        uploaded_now=uploaded_now,
        active_document=active_document,
        active_file_id=active_file_id,
        active_file_name=runtime_file_name,
        active_file_source=active_file_source,
        last_file_chunk_ids=last_file_chunk_ids,
        title=title,
        category=category,
        user_id=user_id,
        kb_version=kb_version,
        top_k=top_k,
    )
    if prepared_runtime["status"] == "error":
        return prepared_runtime

    file_id = prepared_runtime["file_id"]
    active_file_id = str(file_id)
    active_file_name = prepared_runtime["active_file_name"]
    active_file_source = prepared_runtime["active_file_source"]
    text_with_file_mode = prepared_runtime["text_with_file_mode"]
    normalized_text_with_file_mode = str(text_with_file_mode or "").lower()
    refined_context = prepared_runtime["refined_context"]
    retrieved_chunks = prepared_runtime["retrieved_chunks"]
    active_document = prepared_runtime.get("active_document") or active_document
    workflow_question = normalized_question
    if normalized_text_with_file_mode == TEXT_WITH_FILE_MODE_VS_KB:
        workflow_question = build_file_vs_kb_workflow_question(
            original_question=normalized_question,
            refined_context=refined_context,
            file_content=str(input_result.get("file_content", "")),
            retrieved_chunks=retrieved_chunks,
        )
        print(
            "[TEXT_WITH_FILE][FILE_VS_KB] "
            f"mode={text_with_file_mode} "
            f"file={active_file_name} "
            f"workflow_question={workflow_question[:1000]!r}"
        )

    follow_up_state = _build_follow_up_state(
        recent_messages=recent_messages,
        active_file_name=str(active_file_name),
        active_file_id=str(active_file_id),
    )
    workflow_input, comfyui_result = run_workflow_fn(
        input_type="text_with_file",
        question=workflow_question,
        context=refined_context,
        follow_up_state=follow_up_state or initial_follow_up_state,
        question_source_index=1,
    )
    if normalized_text_with_file_mode == TEXT_WITH_FILE_MODE_VS_KB:
        _log_file_vs_kb_workflow_result(
            mode=str(text_with_file_mode),
            file_name=str(active_file_name),
            workflow_question=workflow_question,
            comfyui_result=comfyui_result,
        )

    return {
        "status": "success",
        "input_type": "text_with_file",
        "effective_question": normalized_question,
        "rewrite_applied": False,
        "rewrite_reason": "",
        "follow_up_state": follow_up_state or initial_follow_up_state,
        "question_source_index": 1,
        "refined_context": refined_context,
        "retrieved_chunks": retrieved_chunks,
        "workflow_input": workflow_input,
        "comfyui_result": comfyui_result,
        "file_id": file_id,
        "active_file_id": active_file_id,
        "active_file_name": active_file_name,
        "active_file_mode": text_with_file_mode,
        "active_file_source": active_file_source,
        "active_file_reused": active_file_reused,
        "active_document": active_document,
        "text_with_file_cache_key": "",
    }
