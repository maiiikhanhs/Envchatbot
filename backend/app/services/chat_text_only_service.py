from __future__ import annotations

from app.services.text_only.memory import (
    _build_follow_up_state,
    _latest_router_label_from_history,
    build_text_only_topic_update,
)
from app.services.text_only.policy import (
    GREETING_ANSWER,
    TEXT_ONLY_CACHE_POLICY_VERSION,
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
    UNRELATED_ANSWER,
    VALID_ROUTER_LABELS,
    _build_text_only_cache_kb_version,
    _compact_text,
    _extract_reference,
    _is_unusable_text_only_answer,
    _is_valid_router_label,
    _looks_like_runtime_error_text,
    _looks_like_raw_router_output,
    _should_cache_text_only_answer,
)
from app.services.text_only.resolver import (
    TextOnlyQueryResolution,
    _is_follow_up_question,
)
from app.services.text_only.runtime import handle_text_only_request

__all__ = [
    "GREETING_ANSWER",
    "UNRELATED_ANSWER",
    "TEXT_ONLY_CACHE_POLICY_VERSION",
    "TEXT_ONLY_INVALID_OUTPUT_FALLBACK",
    "VALID_ROUTER_LABELS",
    "TextOnlyQueryResolution",
    "_build_follow_up_state",
    "_build_text_only_cache_kb_version",
    "_compact_text",
    "_extract_reference",
    "_is_follow_up_question",
    "_is_unusable_text_only_answer",
    "_is_valid_router_label",
    "_latest_router_label_from_history",
    "_looks_like_runtime_error_text",
    "_looks_like_raw_router_output",
    "_should_cache_text_only_answer",
    "build_text_only_topic_update",
    "handle_text_only_request",
]
