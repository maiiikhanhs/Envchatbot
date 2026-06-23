from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.text_only.memory import _latest_assistant_answer_from_history
from app.services.text_only.policy import (
    _compact_text,
    _extract_reference,
    _normalize_text_signal,
)

SHORT_QUESTION_TOKEN_LIMIT = 5
TOPIC_CONTINUITY_MIN_OVERLAP = 2
TOPIC_CONTINUITY_SCORE_THRESHOLD = 0.34


@dataclass(frozen=True)
class TextOnlyQueryResolution:
    query_mode: str
    user_question: str
    effective_question: str
    cache_key: str
    reason: str


def _topic_state_has_memory(topic_state: dict, recent_messages: list[dict]) -> bool:
    return bool(
        _compact_text(topic_state.get("active_topic_id", ""))
        or _compact_text(topic_state.get("last_topic_anchor", ""))
        or _compact_text(topic_state.get("last_topic_focus", ""))
        or _latest_assistant_answer_from_history(recent_messages)
    )


def _has_explicit_anchor(question: str) -> bool:
    reference = _extract_reference(question)
    if reference["qcvn"] or reference["instrument"] or reference["article"]:
        return True
    return any(
        len(token) >= 2 and any(char.isalpha() for char in token) and token == token.upper()
        for token in re.findall(r"[A-Za-z0-9]+(?:[.:/-][A-Za-z0-9]+)*", question)
    )


def _tokenize_query(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize_text_signal(text))


def _extract_query_terms(text: str) -> set[str]:
    return {token for token in _tokenize_query(text) if len(token) >= 3 or token.isdigit()}


def _ordered_query_terms(text: str) -> list[str]:
    return [token for token in _tokenize_query(text) if len(token) >= 3 or token.isdigit()]


def _query_term_weight(token: str) -> int:
    return 3 if token.isdigit() or any(char.isdigit() for char in token) or len(token) >= 6 else 2 if len(token) >= 4 else 1


def _has_prefix_framing_overlap(question: str, topic_state: dict, overlap: set[str]) -> bool:
    question_prefix = set(_ordered_query_terms(question)[:4])
    return any(
        len(question_prefix & set(_ordered_query_terms(topic_state.get(key, ""))[:4]) & overlap)
        >= 2
        for key in ("last_topic_focus", "last_topic_effective_question")
    )


def _topic_continuity_score(
    question: str,
    topic_state: dict,
    recent_messages: list[dict],
) -> tuple[float, set[str]]:
    question_terms = _extract_query_terms(question)
    if not question_terms:
        return 0.0, set()

    memory_parts = [
        _compact_text(topic_state.get("last_topic_anchor", "")),
        _compact_text(topic_state.get("last_topic_focus", "")),
        _compact_text(topic_state.get("last_topic_effective_question", "")),
    ]
    for message in recent_messages[-6:]:
        if message.get("role") == "user":
            memory_parts.append(
                _compact_text(message.get("effective_question", ""))
                or _compact_text(message.get("normalized_question", ""))
                or _compact_text(message.get("question", ""))
            )
        elif message.get("role") == "assistant":
            memory_parts.append(_compact_text(message.get("answer", "")))
    memory_terms = _extract_query_terms(" ".join(part for part in memory_parts if part))
    if not memory_terms:
        return 0.0, set()

    overlap = question_terms & memory_terms
    total_weight = sum(_query_term_weight(token) for token in question_terms)
    overlap_weight = sum(_query_term_weight(token) for token in overlap)
    return overlap_weight / total_weight if total_weight else 0.0, overlap


def _should_wrap_with_topic_context(
    question: str,
    topic_state: dict,
    recent_messages: list[dict],
) -> tuple[bool, str]:
    if not _topic_state_has_memory(topic_state, recent_messages):
        return False, "standalone_question"
    if _has_explicit_anchor(question):
        return False, "explicit_anchor"

    token_count = len(_tokenize_query(question))
    if token_count <= SHORT_QUESTION_TOKEN_LIMIT:
        return True, "short_question_with_topic_memory"

    score, overlap = _topic_continuity_score(question, topic_state, recent_messages)
    anchor_overlap = _extract_query_terms(question) & _extract_query_terms(
        topic_state.get("last_topic_anchor", "")
    )
    has_anchor_overlap = any(any(char.isdigit() for char in token) for token in anchor_overlap) or len(anchor_overlap) >= 2
    has_context_overlap = (
        len(overlap) >= 4
        and score >= 0.30
        and not _has_prefix_framing_overlap(question, topic_state, overlap)
    )
    if (
        (
            has_anchor_overlap
            and len(overlap) >= TOPIC_CONTINUITY_MIN_OVERLAP
            and score >= TOPIC_CONTINUITY_SCORE_THRESHOLD
        )
        or has_context_overlap
        or (len(overlap) >= TOPIC_CONTINUITY_MIN_OVERLAP and score >= 0.55)
    ):
        return True, "topic_continuity_overlap"

    return False, "standalone_question"


def _query_resolution(
    query_mode: str,
    user_question: str,
    effective_question: str,
    reason: str,
) -> TextOnlyQueryResolution:
    return TextOnlyQueryResolution(query_mode, user_question, effective_question, effective_question, reason)


def _build_contextual_effective_question(*, question: str, topic_state: dict) -> str:
    topic_parts = []
    for key in ("last_topic_anchor", "last_topic_focus"):
        value = _compact_text(topic_state.get(key, ""))
        if not value:
            continue
        if any(value in existing for existing in topic_parts):
            continue
        topic_parts = [existing for existing in topic_parts if existing not in value]
        topic_parts.append(value)

    topic_context = ". ".join(topic_parts)
    if not topic_context:
        return _compact_text(question)

    return "\n".join(
        [
            f"Ngữ cảnh chủ đề trước: {topic_context}",
            f"Câu hỏi hiện tại: {_compact_text(question)}",
        ]
    ).strip()


def _resolve_text_only_query(
    *,
    question: str,
    topic_state: dict,
    recent_messages: list[dict],
) -> TextOnlyQueryResolution:
    user_question = _compact_text(question)
    if not user_question:
        return _query_resolution("ambiguous", user_question, user_question, "empty_question")

    should_wrap, reason = _should_wrap_with_topic_context(
        user_question,
        topic_state,
        recent_messages,
    )
    if should_wrap:
        effective_question = _build_contextual_effective_question(
            question=user_question,
            topic_state=topic_state,
        )
        return _query_resolution("follow_up", user_question, effective_question, reason)

    return _query_resolution("new_topic", user_question, user_question, reason)


def _is_follow_up_question(question: str, *, topic_state: dict | None = None) -> bool:
    topic_state = topic_state or {}
    should_wrap, _ = _should_wrap_with_topic_context(question, topic_state, [])
    return bool(_compact_text(question)) and should_wrap
