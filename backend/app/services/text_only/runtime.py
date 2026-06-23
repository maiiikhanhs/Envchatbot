from __future__ import annotations

import re
from typing import Callable

from app.services.text_only.memory import (
    _build_conversation_context,
    _build_follow_up_state,
    _resolve_topic_state,
)
from app.services.text_only.policy import (
    SPECIALIST_ROUTER_LABELS,
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
    _compact_text,
    _is_unusable_text_only_answer,
    _looks_like_raw_router_output,
    _looks_like_no_grounding_answer,
    _looks_like_runtime_error_text,
)
from app.services.text_only.resolver import _resolve_text_only_query

TEXT_ONLY_RECOVERY_NODE_IDS = (
    "13",
    "52",
    "12",
    "30",
    "31",
    "32",
    "33",
    "34",
    "5",
    "6",
    "7",
    "8",
    "9",
)
_INTERNAL_LABEL_RE = re.compile(
    r"^\s*\[(PHAP_LY|THONG_SO|QUY_TRINH|HO_SO|VAN_HANH|DIRECT)\]\s*",
    re.IGNORECASE,
)
_SOURCE_MARKER_RE = re.compile(r"\[(?:FILE_)?SOURCE_\d+\]", re.IGNORECASE)


def _extract_history_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_extract_history_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        if "text" in value:
            return _extract_history_text(value.get("text"))
        return "\n".join(_extract_history_text(item) for item in value.values() if item is not None)
    return "" if value is None else str(value)


def _clean_recovered_text_only_answer(text: str) -> str:
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").splitlines()]
    cleaned = "\n".join(line for line in lines if not _looks_like_runtime_error_text(line.strip()))
    cleaned = re.sub(r"<thought\b[^>]*>.*?</thought>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = _INTERNAL_LABEL_RE.sub("", cleaned).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _is_recoverable_text_only_candidate(text: str) -> bool:
    compacted = _compact_text(text)
    if (
        not compacted
        or compacted.startswith("KHONG_PHU_HOP")
        or _looks_like_runtime_error_text(compacted)
        or _looks_like_raw_router_output(compacted)
        or _is_unusable_text_only_answer(compacted)
    ):
        return False
    return bool(_INTERNAL_LABEL_RE.search(text) or _SOURCE_MARKER_RE.search(text))


def _recover_text_only_history_answer(comfyui_result: dict) -> str:
    outputs = ((comfyui_result.get("history") or {}).get("outputs") or {})
    for node_id in TEXT_ONLY_RECOVERY_NODE_IDS:
        raw_candidate = _extract_history_text(outputs.get(node_id))
        if not _is_recoverable_text_only_candidate(raw_candidate):
            continue
        cleaned = _clean_recovered_text_only_answer(raw_candidate)
        if cleaned and not _is_unusable_text_only_answer(cleaned):
            return cleaned
    return ""


def _history_has_source_context(comfyui_result: dict) -> bool:
    history_text = _extract_history_text((comfyui_result.get("history") or {}).get("outputs") or {})
    return bool(_SOURCE_MARKER_RE.search(history_text))


def _recover_text_only_comfyui_result(comfyui_result: dict) -> dict:
    if comfyui_result.get("status") != "success":
        return comfyui_result
    final_output = comfyui_result.get("final_output", "")
    if final_output and not _is_unusable_text_only_answer(final_output):
        return comfyui_result

    recovered_answer = _recover_text_only_history_answer(comfyui_result)
    if not recovered_answer:
        return comfyui_result

    recovered_result = dict(comfyui_result)
    recovered_result["final_output"] = recovered_answer
    recovered_result["recovered_from_history"] = True
    return recovered_result


def _should_retry_text_only_source_grounding(
    *,
    comfyui_result: dict,
    query_mode: str,
) -> bool:
    router_label = _compact_text(comfyui_result.get("router_output", "")).upper()
    final_output = comfyui_result.get("final_output", "")
    return (
        query_mode != "follow_up"
        and router_label in SPECIALIST_ROUTER_LABELS
        and _looks_like_no_grounding_answer(final_output)
        and _history_has_source_context(comfyui_result)
        and not _recover_text_only_history_answer(comfyui_result)
    )


def handle_text_only_request(
    *,
    conversation_id: str,
    question: str,
    normalized_question: str,
    recent_messages: list[dict],
    topic_state: dict,
    text_only_cache_kb_version: str,
    run_workflow_fn: Callable[..., tuple[dict, dict]],
    find_cached_answer_fn: Callable[..., dict | None],
    add_user_message_fn: Callable[..., str],
    add_assistant_message_fn: Callable[..., str],
    lookup_semantic_cached_answer_fn: Callable[..., dict | None] | None = None,
) -> dict:
    topic_state = _resolve_topic_state(topic_state=topic_state, recent_messages=recent_messages)
    resolution = _resolve_text_only_query(
        question=normalized_question or question,
        topic_state=topic_state,
        recent_messages=recent_messages,
    )
    effective_question = resolution.effective_question
    follow_up_state = _build_follow_up_state(
        recent_messages=recent_messages,
        topic_state=topic_state,
    )
    conversation_context = _build_conversation_context(
        topic_state=topic_state,
        recent_messages=recent_messages,
    )
    question_source_index = 1

    if resolution.query_mode in {"needs_clarification", "ambiguous"}:
        workflow_input = {
            "question": effective_question,
            "context": conversation_context,
            "follow_up_state": follow_up_state,
            "question_source_index": question_source_index,
        }
        return {
            "status": "success",
            "input_type": "text_only",
            "effective_question": effective_question,
            "rewrite_applied": False,
            "rewrite_reason": resolution.reason,
            "query_mode": resolution.query_mode,
            "resolution_reason": resolution.reason,
            "follow_up_state": follow_up_state,
            "question_source_index": question_source_index,
            "refined_context": conversation_context,
            "retrieved_chunks": [],
            "workflow_input": workflow_input,
            "comfyui_result": {
                "status": "success",
                "final_output": TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
                "router_output": "",
            },
            "file_id": None,
            "active_file_id": "",
            "active_file_name": "",
            "active_file_mode": "",
            "active_file_source": "",
            "active_file_reused": False,
        }

    cached = find_cached_answer_fn(
        resolution.cache_key,
        kb_version=text_only_cache_kb_version,
    )
    cache_type = "exact"
    if not cached and lookup_semantic_cached_answer_fn is not None:
        cached = lookup_semantic_cached_answer_fn(
            question=effective_question,
            conversation_context=conversation_context,
            kb_version=text_only_cache_kb_version,
        )
        cache_type = "semantic" if cached else "exact"

    if cached:
        cache_context = "[SEMANTIC CACHE HIT]" if cache_type == "semantic" else "[CACHE HIT]"
        add_user_message_fn(
            conversation_id=conversation_id,
            question=question,
            normalized_question=normalized_question,
            effective_question=effective_question,
            input_type="text_only",
            workflow_context=cache_context,
            rewrite_applied=False,
            rewrite_reason=resolution.reason if resolution.query_mode == "follow_up" else "",
        )
        add_assistant_message_fn(
            conversation_id=conversation_id,
            answer=cached["answer"],
            router_label=cached["router_label"],
            workflow_context=cache_context,
        )
        return {
            "status": "cached",
            "response": {
                "status": "success",
                "cached": True,
                "cache_type": cache_type,
                "conversation_id": conversation_id,
                "document_id": None,
                "input_type": "text_only",
                "question": normalized_question,
                "effective_question": effective_question,
                "query_mode": resolution.query_mode,
                "resolution_reason": resolution.reason,
                "workflow_input": {
                    "question": effective_question,
                    "context": conversation_context,
                    "follow_up_state": follow_up_state,
                    "question_source_index": question_source_index,
                },
                "retrieved_count": 0,
                "retrieved_chunks": [],
                "router_output": cached["router_label"],
                "comfyui_result": {
                    "status": "success",
                    "final_output": cached["answer"],
                    "router_output": cached["router_label"],
                },
            },
        }

    workflow_input, comfyui_result = run_workflow_fn(
        input_type="text_only",
        question=effective_question,
        context=conversation_context,
        follow_up_state=follow_up_state,
        question_source_index=question_source_index,
    )
    comfyui_result = _recover_text_only_comfyui_result(comfyui_result)

    if _looks_like_runtime_error_text(
        comfyui_result.get("router_output", "")
    ) and _is_unusable_text_only_answer(comfyui_result.get("final_output", "")):
        workflow_input, comfyui_result = run_workflow_fn(
            input_type="text_only",
            question=effective_question,
            context=conversation_context,
            follow_up_state=follow_up_state,
            question_source_index=question_source_index,
        )
        comfyui_result = _recover_text_only_comfyui_result(comfyui_result)

    if _should_retry_text_only_source_grounding(
        comfyui_result=comfyui_result,
        query_mode=resolution.query_mode,
    ):
        workflow_input, comfyui_result = run_workflow_fn(
            input_type="text_only",
            question=effective_question,
            context=conversation_context,
            follow_up_state=follow_up_state,
            question_source_index=question_source_index,
        )
        comfyui_result = _recover_text_only_comfyui_result(comfyui_result)

    if (
        _looks_like_no_grounding_answer(comfyui_result.get("final_output", ""))
        and conversation_context
        and resolution.query_mode == "follow_up"
        and _compact_text(topic_state.get("active_topic_id", "")) in SPECIALIST_ROUTER_LABELS
    ):
        expanded_context = _build_conversation_context(
            topic_state=topic_state,
            recent_messages=recent_messages,
            max_history_items=12,
            max_chars=4800,
        )
        workflow_input, comfyui_result = run_workflow_fn(
            input_type="text_only",
            question=effective_question,
            context=expanded_context,
            follow_up_state=follow_up_state,
            question_source_index=question_source_index,
        )
        comfyui_result = _recover_text_only_comfyui_result(comfyui_result)
        conversation_context = expanded_context

    return {
        "status": "success",
        "input_type": "text_only",
        "effective_question": effective_question,
        "rewrite_applied": False,
        "rewrite_reason": resolution.reason if resolution.query_mode == "follow_up" else "",
        "query_mode": resolution.query_mode,
        "resolution_reason": resolution.reason,
        "follow_up_state": follow_up_state,
        "question_source_index": question_source_index,
        "refined_context": conversation_context,
        "retrieved_chunks": [],
        "workflow_input": workflow_input,
        "comfyui_result": comfyui_result,
        "file_id": None,
        "active_file_id": "",
        "active_file_name": "",
        "active_file_mode": "",
        "active_file_source": "",
        "active_file_reused": False,
    }
