from __future__ import annotations

import re
import unicodedata

GREETING_ANSWER = "Chào bạn, tôi có thể giúp gì được cho bạn?"

UNRELATED_ANSWER = (
    "Câu hỏi bạn cung cấp không phù hợp với nội dung của chúng tôi, bạn vui lòng đặt câu hỏi khác."
)

TEXT_ONLY_CACHE_POLICY_VERSION = "router_label_v8_source_format"
TEXT_ONLY_INVALID_OUTPUT_FALLBACK = (
    "Câu hỏi hiện tại chưa đủ rõ để xác định đúng yêu cầu. Bạn có thể diễn đạt cụ thể hơn."
)

SPECIALIST_ROUTER_LABELS = {
    "PHAP_LY",
    "THONG_SO",
    "QUY_TRINH",
    "HO_SO",
    "VAN_HANH",
}

VALID_ROUTER_LABELS = SPECIALIST_ROUTER_LABELS | {"XA_GIAO", "KHONG_LIEN_QUAN"}

NON_CACHEABLE_TEXT_ONLY_ANSWERS = {
    "Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",
    "Chưa đủ nội dung trong file được cung cấp để tóm tắt chính xác.",
    "Chưa thấy thông tin này trong file đã cung cấp.",
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
}


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_answer_for_fallback_match(text: str) -> str:
    compacted = _compact_text(text).lower().replace("đ", "d")
    if not compacted:
        return ""
    normalized = unicodedata.normalize("NFKD", compacted)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return _compact_text(ascii_text)


def _normalize_text_signal(text: str) -> str:
    compacted = _compact_text(text).lower().replace("đ", "d")
    if not compacted:
        return ""
    normalized = unicodedata.normalize("NFKD", compacted)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return _compact_text(ascii_text)


def _looks_like_no_grounding_answer(answer: str) -> bool:
    normalized = _normalize_answer_for_fallback_match(answer)
    return normalized.startswith("chua du can cu")


def _looks_like_runtime_error_text(text: str) -> bool:
    compacted = _compact_text(text)
    if not compacted:
        return False
    normalized = _normalize_answer_for_fallback_match(compacted)
    return bool(
        re.search(
            r"(error code|internal error|api error|traceback|exception|resource_exhausted|status['\"]?: ?['\"]?internal|quota exceeded|rate-limit|rate limit|expected string or bytes-like object)",
            normalized,
        )
        or re.search(r"\b(?:429|500|503)\b", compacted)
    )


def _extract_current_question_from_effective(text: str) -> str:
    compacted = _compact_text(text)
    marker = "Câu hỏi hiện tại:"
    if marker in compacted:
        return _compact_text(compacted.rsplit(marker, 1)[-1])
    return compacted


def _extract_reference(text: str) -> dict[str, str]:
    content = _compact_text(text)
    instrument_match = re.search(
        r"\b((?:Nghị định|Thông tư|Luật)\s+\d+(?:/\d+)?/[A-ZĐ0-9-]+)\b",
        content,
        re.IGNORECASE,
    )
    qcvn_match = re.search(
        r"\bQCVN\s*\d+(?::\d+)?(?:/[A-Z0-9-]+)?",
        content,
        re.IGNORECASE,
    )
    article_match = re.search(r"\bĐiều\s+(\d+)\b", content, re.IGNORECASE)
    clause_match = re.search(r"\bKhoản\s+(\d+)\b", content, re.IGNORECASE)
    point_match = re.search(r"\bĐiểm\s+([a-zđ])\b", content, re.IGNORECASE)

    qcvn = qcvn_match.group(0).upper().replace("  ", " ") if qcvn_match else ""
    instrument = instrument_match.group(1) if instrument_match else ""
    article = article_match.group(1) if article_match else ""
    clause = clause_match.group(1) if clause_match else ""
    point = point_match.group(1).lower() if point_match else ""

    parts = [
        f"Điểm {point}" if point else "",
        f"Khoản {clause}" if clause else "",
        f"Điều {article}" if article else "",
    ]
    label = qcvn or instrument or " ".join(part for part in parts if part)

    return {
        "raw": content,
        "lowered": content.lower(),
        "qcvn": qcvn,
        "instrument": instrument,
        "article": article,
        "clause": clause,
        "point": point,
        "label": label,
    }


def _build_text_only_cache_kb_version(kb_version: str) -> str:
    base_version = _compact_text(kb_version) or "v1"
    return f"{base_version}:{TEXT_ONLY_CACHE_POLICY_VERSION}"


def _is_valid_router_label(router_label: str) -> bool:
    return _compact_text(router_label).upper() in VALID_ROUTER_LABELS


def _looks_like_raw_router_output(text: str) -> bool:
    compacted = _compact_text(text)
    return bool(compacted and re.fullmatch(r"[A-Z_]{3,32}", compacted))


def _should_cache_text_only_answer(
    *,
    normalized_question: str,
    final_answer: str,
    router_label: str,
    rewrite_applied: bool,
) -> bool:
    _ = normalized_question
    _ = rewrite_applied
    compacted_answer = _compact_text(final_answer)
    return (
        _is_valid_router_label(router_label)
        and len(compacted_answer) >= 5
        and compacted_answer not in NON_CACHEABLE_TEXT_ONLY_ANSWERS
        and not _looks_like_no_grounding_answer(compacted_answer)
        and not _looks_like_raw_router_output(compacted_answer)
    )


def _is_unusable_text_only_answer(answer: str) -> bool:
    compacted = _compact_text(answer)
    return (
        not compacted
        or compacted in NON_CACHEABLE_TEXT_ONLY_ANSWERS
        or _looks_like_no_grounding_answer(compacted)
        or _looks_like_runtime_error_text(compacted)
        or _looks_like_raw_router_output(compacted)
    )
