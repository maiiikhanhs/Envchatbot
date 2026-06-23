from __future__ import annotations

from dataclasses import dataclass, field

from app.config import TEXT_WITH_FILE_ANSWER_CACHE_ENABLED
from app.services.chat_runtime.answer_policy import (
    build_text_with_file_cache_key,
    normalize_display_answer,
    should_cache_text_with_file_answer,
    text_with_file_content_identity,
)
from app.services.chat_text_only_service import _compact_text, build_text_only_topic_update
from app.services.chat_text_with_file_service import (
    _build_file_info_from_document,
    resolve_active_conversation_file,
)


@dataclass
class ChatRequestState:
    question: str
    normalized_question: str
    conversation_id: str
    input_result: dict
    recent_messages: list[dict]
    topic_state: dict
    active_file_state: dict
    text_only_cache_kb_version: str
    uploaded_now: bool = False
    active_document: dict | None = None
    active_file_id: str = ""
    active_file_name: str = ""
    active_file_source: str = ""
    active_file_reused: bool = False
    last_file_effective_question: str = ""
    last_file_chunk_ids: list[str] = field(default_factory=list)
    last_file_anchor_text: str = ""
    request_state: dict = field(default_factory=dict)
    effective_question: str = ""
    rewrite_applied: bool = False
    rewrite_reason: str = ""
    refined_context: str = ""
    retrieved_chunks: list[dict] = field(default_factory=list)
    workflow_input: dict = field(default_factory=dict)
    comfyui_result: dict = field(default_factory=dict)
    file_id: str = ""
    router_output: str = ""
    text_with_file_mode: str = ""

    def apply_request_state(self, request_state: dict) -> None:
        self.request_state = request_state
        self.effective_question = request_state["effective_question"]
        self.rewrite_applied = request_state["rewrite_applied"]
        self.rewrite_reason = request_state["rewrite_reason"]
        self.refined_context = request_state["refined_context"]
        self.retrieved_chunks = request_state["retrieved_chunks"]
        self.workflow_input = request_state["workflow_input"]
        self.comfyui_result = request_state["comfyui_result"]
        self.file_id = request_state["file_id"]
        self.active_file_id = request_state.get("active_file_id", "")
        self.active_file_name = request_state.get("active_file_name", "")
        self.active_file_source = request_state.get("active_file_source", "")
        self.active_file_reused = request_state.get("active_file_reused", False)
        self.text_with_file_mode = request_state.get("active_file_mode", "")
        self.router_output = ""


def activate_file_input(input_result: dict, document: dict) -> tuple[str, str]:
    input_result["input_type"] = "text_with_file"
    input_result["file_info"] = _build_file_info_from_document(document)
    input_result["file_content"] = ""
    return str(document.get("_id", "")), document.get("original_file_name") or document.get("file_name", "")


def try_resolve_active_file_request(
    *,
    state: ChatRequestState,
    kb_version: str,
    list_file_messages_fn,
    get_document_fn,
    list_document_chunks_fn,
) -> None:
    active_document, active_file_source = resolve_active_conversation_file(
        conversation_id=state.conversation_id,
        question=state.normalized_question,
        kb_version=kb_version,
        active_file_state=state.active_file_state,
        recent_messages=state.recent_messages,
        list_file_messages_fn=list_file_messages_fn,
        get_document_fn=get_document_fn,
        list_document_chunks_fn=list_document_chunks_fn,
    )
    if active_document is None:
        return
    state.active_document = active_document
    state.active_file_source = active_file_source
    state.active_file_id, state.active_file_name = activate_file_input(
        state.input_result,
        active_document,
    )
    state.active_file_reused = True


def _text_with_file_cache_key(
    *,
    question: str,
    mode: str,
    kb_version: str,
    file_id,
    input_result: dict,
    active_document: dict | None,
) -> str:
    return build_text_with_file_cache_key(
        question=question,
        mode=mode,
        kb_version=kb_version,
        file_identity=text_with_file_content_identity(
            input_result=input_result,
            active_document=active_document,
            file_id=str(file_id),
        ),
    )


def lookup_text_with_file_cached_response(
    *,
    normalized_question: str,
    text_with_file_mode: str,
    kb_version: str,
    file_id: str,
    active_document: dict | None,
    input_result: dict,
    find_cached_answer_by_cache_key_fn,
) -> dict | None:
    return None

    if not TEXT_WITH_FILE_ANSWER_CACHE_ENABLED:
        return None

    cache_key = _text_with_file_cache_key(
        question=normalized_question,
        mode=text_with_file_mode,
        kb_version=kb_version,
        file_id=file_id,
        input_result=input_result,
        active_document=active_document,
    )
    if not cache_key:
        return None

    cached = find_cached_answer_by_cache_key_fn(cache_key, kb_version=kb_version)
    if cached and should_cache_text_with_file_answer(
        cached.get("answer", ""),
        cached.get("router_label", ""),
    ):
        print("[CACHE] text_with_file hit")
        return cached
    return None


def handle_text_only_cached_response(
    *,
    state: ChatRequestState,
    request_state: dict,
    timings: dict[str, int],
    total_started_at: float,
    elapsed_ms_fn,
    log_chat_latency_fn,
    list_recent_messages_fn,
    update_conversation_topic_state_fn,
) -> dict:
    cached_response = request_state["response"]
    cached_router_label = _compact_text(cached_response.get("router_output", ""))
    cached_comfyui_result = cached_response.get("comfyui_result") or {}
    cached_answer = normalize_display_answer(cached_comfyui_result.get("final_output", ""))
    cached_comfyui_result["final_output"] = cached_answer
    cached_response["comfyui_result"] = cached_comfyui_result

    topic_update = build_text_only_topic_update(
        previous_topic_state=state.topic_state,
        recent_messages=list_recent_messages_fn(state.conversation_id, limit=3),
        effective_question=cached_response.get(
            "effective_question",
            state.normalized_question,
        ),
        final_answer=cached_answer,
        router_label=cached_router_label,
    )
    update_conversation_topic_state_fn(state.conversation_id, **topic_update)
    timings["total"] = elapsed_ms_fn(total_started_at)
    log_chat_latency_fn(
        timings,
        input_type="text_only",
        status="cached",
        cache_type=cached_response.get("cache_type", "exact"),
    )
    return cached_response


def store_text_with_file_cache(
    *,
    state: ChatRequestState,
    final_answer: str,
    final_router_label: str,
    kb_version: str,
    store_cached_answer_fn,
) -> None:
    return

    if not (
        TEXT_WITH_FILE_ANSWER_CACHE_ENABLED
        and state.request_state["input_type"] == "text_with_file"
        and should_cache_text_with_file_answer(final_answer, final_router_label)
    ):
        return

    cache_key = _text_with_file_cache_key(
        question=state.effective_question,
        mode=state.text_with_file_mode,
        kb_version=kb_version,
        file_id=str(state.file_id),
        input_result=state.input_result,
        active_document=state.request_state.get("active_document"),
    )
    if cache_key:
        store_cached_answer_fn(
            question=state.effective_question,
            normalized_question=cache_key,
            answer=final_answer,
            router_label=final_router_label,
            kb_version=kb_version,
            source_type="text_with_file",
        )


def build_chat_response(
    *,
    state: ChatRequestState,
) -> dict:
    request_state = state.request_state
    is_text_with_file = request_state["input_type"] == "text_with_file"
    return {
        "status": "success",
        "conversation_id": state.conversation_id,
        "document_id": state.file_id,
        "input_type": request_state["input_type"],
        "question": state.normalized_question,
        "effective_question": state.effective_question,
        "query_mode": request_state.get("query_mode", ""),
        "resolution_reason": request_state.get("resolution_reason", ""),
        "workflow_input": state.workflow_input,
        "active_file_id": state.file_id if is_text_with_file else None,
        "active_file_name": state.active_file_name if is_text_with_file else "",
        "active_file_mode": state.text_with_file_mode if is_text_with_file else "",
        "active_file_source": state.active_file_source if is_text_with_file else "",
        "active_file_reused": state.active_file_reused if is_text_with_file else False,
        "retrieved_count": len(state.retrieved_chunks),
        "retrieved_chunks": state.retrieved_chunks,
        "router_output": state.router_output,
        "comfyui_result": state.comfyui_result,
    }
