from __future__ import annotations

from collections.abc import Callable

from app.services.chat_text_only_service import _compact_text
from app.services.chat_runtime.answer_policy import (
    finalize_comfyui_response,
    is_unusable_text_with_file_answer,
    looks_like_workflow_runtime_error_text,
    normalize_display_answer,
    sanitize_final_response,
)
from app.services.text_with_file.assessment import build_file_vs_kb_retry_question
from app.services.text_with_file.context import TEXT_WITH_FILE_MODE_VS_KB

TEXT_WITH_FILE_RECOVERY_NODE_IDS = (
    "33",
    "32",
    "31",
    "18",
    "30",
    "20",
    "13",
    "28",
    "26",
    "17",
    "16",
    "11",
)


def history_contains_runtime_error(value) -> bool:
    if isinstance(value, str):
        return looks_like_workflow_runtime_error_text(value)
    if isinstance(value, dict):
        return any(history_contains_runtime_error(item) for item in value.values())
    if isinstance(value, list):
        return any(history_contains_runtime_error(item) for item in value)
    return False


def extract_history_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(extract_history_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        if "text" in value:
            return extract_history_text(value.get("text"))
        return "\n".join(extract_history_text(item) for item in value.values() if item is not None)
    return "" if value is None else str(value)


def recover_text_with_file_history_answer(comfyui_result: dict) -> str:
    outputs = ((comfyui_result.get("history") or {}).get("outputs") or {})
    for node_id in TEXT_WITH_FILE_RECOVERY_NODE_IDS:
        candidate = normalize_display_answer(extract_history_text(outputs.get(node_id)))
        if candidate and not is_unusable_text_with_file_answer(candidate):
            return candidate
    return ""


def preview_workflow_result(
    *,
    input_type: str,
    comfyui_result: dict,
    retrieved_chunks: list[dict],
) -> tuple[str, str, list[dict]]:
    preview_router_label = _compact_text(comfyui_result.get("router_output", ""))
    preview_answer, preview_chunks = finalize_comfyui_response(
        router_output=preview_router_label,
        raw_answer=comfyui_result.get("final_output", ""),
        retrieved_chunks=retrieved_chunks,
    )
    if input_type == "text_with_file" and is_unusable_text_with_file_answer(preview_answer):
        recovered_answer = recover_text_with_file_history_answer(comfyui_result)
        if recovered_answer:
            preview_answer = recovered_answer
    return sanitize_final_response(
        input_type=input_type,
        router_output=preview_router_label,
        final_answer=preview_answer,
        retrieved_chunks=preview_chunks,
    )


def should_retry_text_with_file_workflow_result(request_state: dict) -> bool:
    if request_state.get("input_type") != "text_with_file":
        return False

    comfyui_result = request_state.get("comfyui_result") or {}
    if comfyui_result.get("status") != "success":
        return False

    preview_answer, _, _ = preview_workflow_result(
        input_type="text_with_file",
        comfyui_result=comfyui_result,
        retrieved_chunks=request_state.get("retrieved_chunks", []),
    )
    if not is_unusable_text_with_file_answer(preview_answer):
        return False

    return bool(request_state.get("retrieved_chunks")) or history_contains_runtime_error(comfyui_result.get("history", {}))


def retry_text_with_file_workflow_once(
    request_state: dict,
    *,
    run_workflow_fn: Callable[..., tuple[dict, dict]],
) -> dict:
    if not should_retry_text_with_file_workflow_result(request_state):
        return request_state

    workflow_input = request_state.get("workflow_input") or {}
    retry_question = workflow_input.get("question", request_state.get("effective_question", ""))
    if str(request_state.get("active_file_mode", "")).lower() == TEXT_WITH_FILE_MODE_VS_KB:
        strict_question = build_file_vs_kb_retry_question(
            original_question=retry_question,
            refined_context=workflow_input.get("context", request_state.get("refined_context", "")),
            retrieved_chunks=request_state.get("retrieved_chunks", []),
        )
        if strict_question:
            retry_question = strict_question

    _, retry_result = run_workflow_fn(
        input_type="text_with_file",
        question=retry_question,
        context=workflow_input.get("context", request_state.get("refined_context", "")),
        follow_up_state=workflow_input.get("follow_up_state", ""),
        question_source_index=workflow_input.get("question_source_index", 1),
    )

    if retry_result.get("status") != "success":
        return request_state

    retry_answer, _, _ = preview_workflow_result(
        input_type="text_with_file",
        comfyui_result=retry_result,
        retrieved_chunks=request_state.get("retrieved_chunks", []),
    )
    strict_retry_used = retry_question != workflow_input.get("question", request_state.get("effective_question", ""))
    if is_unusable_text_with_file_answer(retry_answer) and not strict_retry_used:
        return request_state

    retry_result = dict(retry_result)
    retry_result["final_output"] = retry_answer
    updated_state = dict(request_state)
    updated_state["comfyui_result"] = retry_result
    if strict_retry_used:
        updated_workflow_input = dict(workflow_input)
        updated_workflow_input["question"] = retry_question
        updated_state["workflow_input"] = updated_workflow_input
    return updated_state
