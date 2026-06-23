from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from typing import Callable

from app.services.chat_text_only_service import (
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
    _compact_text,
    _extract_reference,
    _latest_router_label_from_history,
)
from app.services.text_with_file.context import (
    TEXT_WITH_FILE_MODE_QA,
    TEXT_WITH_FILE_MODE_SUMMARY,
    TEXT_WITH_FILE_MODE_VS_KB,
    _build_file_anchor_text,
    _get_chunks_by_ids,
    _normalize_chunk_ids,
)

TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK = "Chưa xác định được yêu cầu cụ thể từ câu hỏi hiện tại trong file đang sử dụng. Bạn có thể nêu rõ phần hoặc nội dung cần hỏi."

VALID_TEXT_WITH_FILE_ROUTER_LABELS = {
    "PHAP_LY", "THONG_SO", "QUY_TRINH", "HO_SO", "VAN_HANH",
    "XA_GIAO", "KHONG_LIEN_QUAN", "FILE_SUMMARY", "FILE_QA", "FILE_VS_KB",
}
FILE_MODE_ROUTER_LABELS = {"FILE_SUMMARY", "FILE_QA", "FILE_VS_KB"}

FILE_SEMANTIC_ROUTE_THRESHOLD = 0.62
FILE_BACKFILL_ROUTE_THRESHOLD = 0.35
SHORT_CONTEXTUAL_TOKEN_LIMIT = 7


def _get_active_file_id(active_file_state: dict) -> str:
    return _compact_text(active_file_state.get("active_file_id", ""))


def _normalize_answer_for_fallback_match(text: str) -> str:
    compacted = _compact_text(text).lower()
    if not compacted:
        return ""
    compacted = compacted.replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", compacted)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _tokenize_terms(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", _normalize_answer_for_fallback_match(text))
        if len(token) >= 2 or token.isdigit()
    ]


def _term_set(text: str) -> set[str]:
    return set(_tokenize_terms(text))


def _looks_like_text_only_no_grounding_answer(answer: str) -> bool:
    normalized = _normalize_answer_for_fallback_match(answer)
    return normalized.startswith("chua du can cu tu d") and "lieu goc" in normalized and "tra loi chinh xac cau hoi nay" in normalized


def _is_text_only_file_retry_candidate(answer: str) -> bool:
    compact_answer = _compact_text(answer)
    return compact_answer == TEXT_ONLY_INVALID_OUTPUT_FALLBACK or _looks_like_text_only_no_grounding_answer(compact_answer)


def _normalize_filename_for_match(text: str) -> str:
    normalized = str(text or "").strip().lower().rsplit(".", 1)[0]
    normalized = re.sub(r"[_\-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _build_file_name_match_tokens(document: dict) -> set[str]:
    tokens = set()
    for field in ("original_file_name", "title", "file_name"):
        normalized = _normalize_filename_for_match(document.get(field, ""))
        if not normalized:
            continue
        words = normalized.split()
        tokens.add(normalized)
        if len(words) > 1:
            tokens.add(" ".join(words[:2]))
        if words:
            tokens.add(words[0])
    return {token for token in tokens if len(token) >= 2 or token in {_normalize_filename_for_match(document.get(field, "")) for field in ("original_file_name", "title", "file_name")}}


def _question_mentions_document(question: str, document: dict) -> bool:
    normalized_question = f" {_normalize_filename_for_match(question)} "
    return bool(normalized_question.strip()) and any(
        f" {token} " in normalized_question for token in _build_file_name_match_tokens(document)
    )


def _has_file_reference_signal(question: str, active_file_name: str = "") -> bool:
    active_document = {"title": active_file_name, "file_name": active_file_name, "original_file_name": active_file_name}
    if active_file_name and _question_mentions_document(question, active_document):
        return True
    return bool(re.search(r"\b(file|tai lieu)\b", _normalize_answer_for_fallback_match(question)))


def _list_conversation_documents(
    conversation_id: str,
    *,
    list_file_messages_fn: Callable[..., list[dict]],
    get_document_fn: Callable[[str], dict | None],
) -> list[dict]:
    candidates = []
    seen_document_ids = set()
    for message in list_file_messages_fn(conversation_id, limit=50):
        document_id = str(message.get("file_id") or "").strip()
        if not document_id or document_id in seen_document_ids:
            continue
        seen_document_ids.add(document_id)
        document = get_document_fn(document_id)
        if document:
            candidates.append(document)
    return candidates


def _resolve_named_conversation_document(
    *,
    conversation_id: str,
    question: str,
    list_file_messages_fn: Callable[..., list[dict]],
    get_document_fn: Callable[[str], dict | None],
) -> tuple[dict | None, str]:
    for document in _list_conversation_documents(
        conversation_id,
        list_file_messages_fn=list_file_messages_fn,
        get_document_fn=get_document_fn,
    ):
        if _question_mentions_document(question, document):
            return document, "matched_by_name"
    return None, ""


def _resolve_latest_conversation_document(
    conversation_id: str,
    *,
    list_file_messages_fn: Callable[..., list[dict]],
    get_document_fn: Callable[[str], dict | None],
) -> dict | None:
    candidates = _list_conversation_documents(
        conversation_id,
        list_file_messages_fn=list_file_messages_fn,
        get_document_fn=get_document_fn,
    )
    return candidates[0] if candidates else None


@lru_cache(maxsize=256)
def _embedding_vector(text: str) -> tuple[float, ...]:
    try:
        from app.retrieval.embedding import generate_real_embedding

        return tuple(float(value) for value in generate_real_embedding(text))
    except Exception:
        return ()


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _lexical_similarity(left: str, right: str) -> float:
    left_terms = _term_set(left)
    right_terms = _term_set(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(len(left_terms), 1)


def _semantic_similarity(left: str, right: str) -> float:
    left_text = _compact_text(left)
    right_text = _compact_text(right)
    if not left_text or not right_text:
        return 0.0
    semantic_score = _cosine_similarity(_embedding_vector(left_text), _embedding_vector(right_text))
    return max(semantic_score, _lexical_similarity(left_text, right_text))


def _latest_file_mode_text_anchor(recent_messages: list[dict]) -> str:
    latest_answer = ""
    latest_question = ""
    for message in reversed(recent_messages):
        role = message.get("role")
        if role == "assistant" and not latest_answer:
            latest_answer = _compact_text(message.get("answer", ""))
        elif role == "user" and not latest_question:
            latest_question = (
                _compact_text(message.get("effective_question", ""))
                or _compact_text(message.get("normalized_question", ""))
                or _compact_text(message.get("question", ""))
            )
        if latest_answer and latest_question:
            break
    return _compact_text(f"{latest_question} {latest_answer}")


def _get_file_follow_up_anchor_text(
    *,
    active_file_state: dict,
    recent_messages: list[dict],
    list_document_chunks_fn: Callable[..., list[dict]],
) -> str:
    anchor_text = _compact_text(active_file_state.get("last_file_anchor_text", ""))
    if anchor_text:
        return anchor_text

    active_file_id = _get_active_file_id(active_file_state)
    chunk_ids = _normalize_chunk_ids(active_file_state.get("last_file_chunk_ids", []))
    if active_file_id and chunk_ids:
        chunk_anchor = _build_file_anchor_text(
            retrieved_chunks=_get_chunks_by_ids(list_document_chunks_fn(active_file_id), chunk_ids),
        )
        if chunk_anchor:
            return chunk_anchor

    return _latest_file_mode_text_anchor(recent_messages) or _compact_text(active_file_state.get("last_file_effective_question", ""))


def _build_file_memory_text(
    *,
    active_file_state: dict,
    recent_messages: list[dict],
    list_document_chunks_fn: Callable[..., list[dict]],
) -> str:
    return _compact_text(
        " ".join(
            part
            for part in (
                active_file_state.get("active_file_name", ""),
                active_file_state.get("last_file_effective_question", ""),
                _get_file_follow_up_anchor_text(
                    active_file_state=active_file_state,
                    recent_messages=recent_messages,
                    list_document_chunks_fn=list_document_chunks_fn,
                ),
            )
            if _compact_text(part)
        )
    )


def _has_explicit_new_reference(question: str, file_memory: str = "") -> bool:
    reference = _extract_reference(question)
    if reference["qcvn"] or reference["instrument"] or reference["article"] or reference["clause"] or reference["point"]:
        return _semantic_similarity(question, file_memory) < FILE_SEMANTIC_ROUTE_THRESHOLD

    memory_terms = _term_set(file_memory)
    uppercase_tokens = [
        token.lower()
        for token in re.findall(r"[A-ZĐ]{2,}[A-ZĐ0-9./:-]*", question)
        if any(char.isalpha() for char in token)
    ]
    return bool(uppercase_tokens) and not any(token in memory_terms for token in uppercase_tokens)


def _is_context_dependent(question: str) -> bool:
    terms = _tokenize_terms(question)
    return bool(terms) and len(terms) <= SHORT_CONTEXTUAL_TOKEN_LIMIT


def _is_standalone_anchor_question(question: str) -> bool:
    return len(_tokenize_terms(question)) <= SHORT_CONTEXTUAL_TOKEN_LIMIT and bool(
        re.search(r"\b[A-ZĐ0-9./:-]*[A-ZĐ]{2,}[A-ZĐ0-9./:-]*\b", question)
    )


def _looks_like_file_vs_kb_assessment_question(question: str) -> bool:
    normalized = _normalize_answer_for_fallback_match(question)
    return bool(
        re.search(
            r"(dat\s+hay\s+chua\s+dat|"
            r"danh\s+gia.*\bdat\b|"
            r"\bco\s+dat\b|"
            r"\bchua\s+dat\b|"
            r"doi\s+chieu|"
            r"so\s+sanh|"
            r"phu\s+hop.*(?:qcvn|quy\s+chuan)|"
            r"theo\s+quy\s+chuan.*(?:dat|phu\s+hop))",
            normalized,
        )
    )


def _classify_text_with_file_mode(question: str) -> str:
    terms = _term_set(question)
    if {"tom", "tat"} <= terms:
        return TEXT_WITH_FILE_MODE_SUMMARY
    if _looks_like_file_vs_kb_assessment_question(question):
        return TEXT_WITH_FILE_MODE_VS_KB
    reference = _extract_reference(question)
    if not _is_context_dependent(question) and any(
        reference[key] for key in ("qcvn", "instrument", "article", "clause", "point")
    ):
        return TEXT_WITH_FILE_MODE_VS_KB
    return TEXT_WITH_FILE_MODE_QA


def _should_use_active_file(
    *,
    question: str,
    active_file_state: dict,
    recent_messages: list[dict],
    list_document_chunks_fn: Callable[..., list[dict]],
) -> bool:
    active_label = (
        _latest_router_label_from_history(recent_messages)
        or _compact_text(active_file_state.get("active_file_mode", "")).upper()
    )
    if not _get_active_file_id(active_file_state) or active_label not in FILE_MODE_ROUTER_LABELS:
        return False

    active_file_name = _compact_text(active_file_state.get("active_file_name", ""))
    has_file_signal = _has_file_reference_signal(question, active_file_name)
    if has_file_signal:
        return True
    if _is_standalone_anchor_question(question):
        return False

    file_memory = _build_file_memory_text(
        active_file_state=active_file_state,
        recent_messages=recent_messages,
        list_document_chunks_fn=list_document_chunks_fn,
    )

    if _semantic_similarity(question, file_memory) >= FILE_SEMANTIC_ROUTE_THRESHOLD:
        return True
    if _classify_text_with_file_mode(question) in {TEXT_WITH_FILE_MODE_SUMMARY, TEXT_WITH_FILE_MODE_VS_KB}:
        return True
    if _has_explicit_new_reference(question, file_memory):
        return False
    return _is_context_dependent(question)


def should_route_to_text_with_file(
    *,
    question: str,
    active_file_state: dict,
    recent_messages: list[dict],
    list_document_chunks_fn: Callable[..., list[dict]],
) -> bool:
    return bool(_get_active_file_id(active_file_state)) and _should_use_active_file(
        question=question,
        active_file_state=active_file_state,
        recent_messages=recent_messages,
        list_document_chunks_fn=list_document_chunks_fn,
    )


def should_retry_as_text_with_file(
    *,
    active_file_state: dict,
    recent_messages: list[dict],
    question: str,
    final_answer: str,
    list_document_chunks_fn: Callable[..., list[dict]],
) -> bool:
    return (
        bool(_get_active_file_id(active_file_state))
        and _is_text_only_file_retry_candidate(final_answer)
        and should_route_to_text_with_file(
            question=question,
            active_file_state=active_file_state,
            recent_messages=recent_messages,
            list_document_chunks_fn=list_document_chunks_fn,
        )
    )


def resolve_active_conversation_file(
    *,
    conversation_id: str,
    question: str,
    kb_version: str,
    active_file_state: dict,
    recent_messages: list[dict],
    list_file_messages_fn: Callable[..., list[dict]],
    get_document_fn: Callable[[str], dict | None],
    list_document_chunks_fn: Callable[..., list[dict]],
) -> tuple[dict | None, str]:
    _ = kb_version
    matched_document, matched_source = _resolve_named_conversation_document(
        conversation_id=conversation_id,
        question=question,
        list_file_messages_fn=list_file_messages_fn,
        get_document_fn=get_document_fn,
    )
    if matched_document is not None:
        return matched_document, matched_source

    active_file_id = _get_active_file_id(active_file_state)
    if active_file_id and should_route_to_text_with_file(
        question=question,
        active_file_state=active_file_state,
        recent_messages=recent_messages,
        list_document_chunks_fn=list_document_chunks_fn,
    ):
        active_document = get_document_fn(active_file_id)
        if active_document:
            return active_document, "active"

    latest_document = _resolve_latest_conversation_document(
        conversation_id,
        list_file_messages_fn=list_file_messages_fn,
        get_document_fn=get_document_fn,
    )
    latest_document_id = str((latest_document or {}).get("_id", "")).strip()
    latest_document_chunks = (
        list_document_chunks_fn(latest_document_id, kb_version=kb_version)
        if latest_document_id
        else []
    )
    latest_memory = _build_file_memory_text(
        active_file_state=active_file_state,
        recent_messages=recent_messages,
        list_document_chunks_fn=list_document_chunks_fn,
    ) or " ".join(
        _compact_text(latest_document.get(field, ""))
        for field in ("original_file_name", "title", "file_name")
        if latest_document
    )
    latest_memory = _compact_text(
        f"{latest_memory} {_build_file_anchor_text(retrieved_chunks=latest_document_chunks)}"
    )
    has_new_reference = _has_explicit_new_reference(question, latest_memory)
    has_file_signal = _has_file_reference_signal(
        question,
        latest_document.get("original_file_name", "") if latest_document else "",
    )
    if latest_document and not has_new_reference and not (
        _is_standalone_anchor_question(question) and not has_file_signal
    ) and (
        _is_context_dependent(question)
        or _classify_text_with_file_mode(question) != TEXT_WITH_FILE_MODE_QA
        or _semantic_similarity(question, latest_memory) >= FILE_BACKFILL_ROUTE_THRESHOLD
    ):
        return latest_document, "backfilled_latest"
    return None, ""


def _build_file_info_from_document(document: dict) -> dict:
    return {
        "file_id": str(document.get("_id", "")),
        "file_name": document.get("file_name", ""),
        "original_file_name": document.get("original_file_name", ""),
        "file_path": document.get("file_path", ""),
        "file_type": document.get("file_type", ""),
    }
