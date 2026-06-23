from __future__ import annotations

from app.services.text_only.policy import (
    SPECIALIST_ROUTER_LABELS,
    _compact_text,
    _extract_current_question_from_effective,
    _extract_reference,
)


def _latest_router_label_from_history(recent_messages: list[dict]) -> str:
    for message in reversed(recent_messages):
        if message.get("role") == "assistant":
            router_label = _compact_text(message.get("router_label", "")).upper()
            if router_label:
                return router_label
    return ""


def _latest_assistant_answer_from_history(recent_messages: list[dict]) -> str:
    for message in reversed(recent_messages):
        if message.get("role") == "assistant":
            answer = _compact_text(message.get("answer", ""))
            if answer:
                return answer
    return ""


def _latest_effective_question_from_history(recent_messages: list[dict]) -> str:
    for message in reversed(recent_messages):
        if message.get("role") != "user":
            continue
        for field in ("effective_question", "normalized_question", "question"):
            candidate = _compact_text(message.get(field, ""))
            if candidate:
                return candidate
    return ""


def _build_topic_anchor_text(*, effective_question: str, final_answer: str) -> str:
    reference = _extract_reference(f"{effective_question} {final_answer}")
    if reference["qcvn"] or reference["instrument"] or reference["label"]:
        return reference["qcvn"] or reference["instrument"] or reference["label"]
    return (_compact_text(effective_question) or _compact_text(final_answer))[:180].strip()


def _build_topic_focus_text(*, effective_question: str, final_answer: str) -> str:
    return (_compact_text(effective_question) or _compact_text(final_answer))[:240].strip()


def _build_topic_history_buffer(
    recent_messages: list[dict],
    *,
    max_items: int = 6,
) -> list[dict]:
    buffer: list[dict] = []
    for message in recent_messages[-max_items:]:
        role = message.get("role")
        if role == "user":
            content = _extract_current_question_from_effective(
                _compact_text(message.get("effective_question", ""))
                or _compact_text(message.get("normalized_question", ""))
                or _compact_text(message.get("question", ""))
            )
            if content:
                buffer.append({"role": "user", "content": content})
        elif role == "assistant":
            content = _compact_text(message.get("answer", ""))
            if content:
                buffer.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "router_label": _compact_text(message.get("router_label", "")),
                    }
                )
    return buffer


def _serialize_topic_history_buffer(topic_history_buffer: list[dict]) -> str:
    lines: list[str] = []
    for item in topic_history_buffer:
        content = _compact_text(item.get("content", ""))
        if not content:
            continue
        if item.get("role") == "assistant":
            router_label = _compact_text(item.get("router_label", ""))
            label = f"Assistant[{router_label}]" if router_label else "Assistant"
            lines.append(f"- {label}: {content}")
        else:
            lines.append(f"- User: {content}")
    return "\n".join(lines)


def _resolve_topic_state(*, topic_state: dict, recent_messages: list[dict]) -> dict:
    resolved = {
        "active_topic_id": _compact_text(topic_state.get("active_topic_id", "")),
        "last_topic_anchor": _compact_text(topic_state.get("last_topic_anchor", "")),
        "last_topic_focus": _compact_text(topic_state.get("last_topic_focus", "")),
        "last_topic_effective_question": _compact_text(
            topic_state.get("last_topic_effective_question", "")
        ),
        "topic_history_buffer": list(topic_state.get("topic_history_buffer") or []),
    }

    latest_router = _latest_router_label_from_history(recent_messages)
    if not resolved["active_topic_id"] and latest_router in SPECIALIST_ROUTER_LABELS:
        resolved["active_topic_id"] = latest_router
    if not resolved["last_topic_effective_question"]:
        resolved["last_topic_effective_question"] = _latest_effective_question_from_history(
            recent_messages
        )

    latest_answer = _latest_assistant_answer_from_history(recent_messages)
    if not resolved["last_topic_anchor"]:
        resolved["last_topic_anchor"] = _build_topic_anchor_text(
            effective_question=resolved["last_topic_effective_question"],
            final_answer=latest_answer,
        )
    if not resolved["last_topic_focus"]:
        resolved["last_topic_focus"] = _build_topic_focus_text(
            effective_question=resolved["last_topic_effective_question"],
            final_answer=latest_answer,
        )
    if not resolved["topic_history_buffer"]:
        resolved["topic_history_buffer"] = _build_topic_history_buffer(recent_messages)

    return resolved


def _build_conversation_context(
    *,
    topic_state: dict,
    recent_messages: list[dict],
    max_history_items: int = 6,
    max_chars: int = 3200,
) -> str:
    topic_state = _resolve_topic_state(topic_state=topic_state or {}, recent_messages=recent_messages)
    history_buffer = _build_topic_history_buffer(recent_messages, max_items=max_history_items)
    if not history_buffer:
        history_buffer = list(topic_state.get("topic_history_buffer") or [])[-max_history_items:]

    lines: list[str] = []
    active_topic_id = _compact_text(topic_state.get("active_topic_id", ""))
    last_topic_anchor = _compact_text(topic_state.get("last_topic_anchor", ""))
    last_topic_focus = _compact_text(topic_state.get("last_topic_focus", ""))
    last_topic_effective_question = _compact_text(
        topic_state.get("last_topic_effective_question", "")
    )
    latest_answer = _latest_assistant_answer_from_history(recent_messages)

    if active_topic_id:
        lines.append(f"- Active topic: {active_topic_id}")
    if last_topic_anchor:
        lines.append(f"- Topic anchor: {last_topic_anchor}")
    if last_topic_focus:
        lines.append(f"- Topic focus: {last_topic_focus}")
    if last_topic_effective_question:
        lines.append(f"- Previous user question: {last_topic_effective_question}")
    if latest_answer:
        lines.append(f"- Previous assistant answer: {latest_answer}")

    serialized_history = _serialize_topic_history_buffer(history_buffer)
    if serialized_history:
        lines.append("- Recent memory:")
        lines.append(serialized_history)

    if not lines:
        return ""

    context = "\n".join(
        [
            "Conversation memory:",
            *lines,
            "",
            "Instruction:",
            "Use this memory only if it is relevant to the current question.",
            "If it is not relevant, answer the current question independently.",
        ]
    )
    return context[:max_chars].strip()


def _build_follow_up_state(
    *,
    recent_messages: list[dict],
    topic_state: dict | None = None,
    active_file_name: str = "",
    active_file_id: str = "",
) -> str:
    topic_state = _resolve_topic_state(
        topic_state=topic_state or {},
        recent_messages=recent_messages,
    )
    lines = []
    for label, key in (
        ("Active Topic Id", "active_topic_id"),
        ("Last Topic Anchor", "last_topic_anchor"),
        ("Last Topic Focus", "last_topic_focus"),
        ("Last Topic Effective Question", "last_topic_effective_question"),
    ):
        value = _compact_text(topic_state.get(key, ""))
        if value:
            lines.append(f"{label}: {value}")
            if key == "last_topic_anchor":
                lines.append(f"Latest Anchor: {value}")
            elif key == "last_topic_effective_question":
                lines.append(f"Latest Effective Question: {value}")

    latest_router = _latest_router_label_from_history(recent_messages)
    if latest_router:
        lines.append(f"Latest Router Label: {latest_router}")
    if active_file_name:
        lines.append(f"Active File Name: {active_file_name}")
    if active_file_id:
        lines.append(f"Active File Id: {active_file_id}")

    history = _serialize_topic_history_buffer(topic_state.get("topic_history_buffer") or [])
    if history:
        lines.append("Topic History Buffer:")
        lines.append(history)
    return "\n".join(lines).strip()


def build_text_only_topic_update(
    *,
    previous_topic_state: dict,
    recent_messages: list[dict],
    effective_question: str,
    final_answer: str,
    router_label: str,
) -> dict:
    compact_router = _compact_text(router_label).upper()
    topic_effective_question = _extract_current_question_from_effective(effective_question)
    if compact_router not in SPECIALIST_ROUTER_LABELS:
        preserved = {
            key: _compact_text(previous_topic_state.get(key, ""))
            for key in (
                "active_topic_id",
                "last_topic_anchor",
                "last_topic_focus",
                "last_topic_effective_question",
            )
        }
        return preserved | {"topic_history_buffer": _build_topic_history_buffer(recent_messages)}

    return {
        "active_topic_id": compact_router,
        "last_topic_anchor": _build_topic_anchor_text(
            effective_question=topic_effective_question,
            final_answer=final_answer,
        ),
        "last_topic_focus": _build_topic_focus_text(
            effective_question=topic_effective_question,
            final_answer=final_answer,
        ),
        "last_topic_effective_question": topic_effective_question,
        "topic_history_buffer": _build_topic_history_buffer(recent_messages),
    }
