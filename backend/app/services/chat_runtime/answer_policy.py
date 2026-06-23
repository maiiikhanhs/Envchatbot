from __future__ import annotations

import html
import hashlib
import re

from app.services.chat_text_only_service import (
    GREETING_ANSWER,
    TEXT_ONLY_INVALID_OUTPUT_FALLBACK,
    UNRELATED_ANSWER,
    _compact_text,
    _is_unusable_text_only_answer,
    _is_valid_router_label,
    _looks_like_raw_router_output,
    _looks_like_runtime_error_text,
)
from app.services.chat_text_with_file_service import (
    TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK,
    VALID_TEXT_WITH_FILE_ROUTER_LABELS,
)

_THOUGHT_BLOCK_RE = re.compile(r"<thought\b[^>]*>.*?</thought>", re.IGNORECASE | re.DOTALL)
TEXT_ONLY_ROUTER_LABELS = (
    "PHAP_LY",
    "THONG_SO",
    "QUY_TRINH",
    "HO_SO",
    "VAN_HANH",
    "XA_GIAO",
    "KHONG_LIEN_QUAN",
)


def strip_model_thought_blocks(text: str) -> str:
    content = str(text or "")
    previous = None
    while previous != content:
        previous = content
        content = _THOUGHT_BLOCK_RE.sub("", content)
    return re.sub(r"</?thought\b[^>]*>", "", content, flags=re.IGNORECASE)


def looks_like_workflow_runtime_error_text(text: str) -> bool:
    compacted = _compact_text(text)
    if not compacted:
        return False
    normalized = compacted.lower().replace("đ", "d")
    has_error_context = bool(
        re.search(
            r"(error code|internal error|api error|traceback|exception|resource_exhausted|unavailable|high demand|quota exceeded|rate-limit|rate limit|status['\"]?:|expected string or bytes-like object)",
            normalized,
        )
    )
    return has_error_context or bool(
        re.search(r"\b(?:429|500|503)\b", compacted)
        and re.search(r"(error|status|code|internal|unavailable)", normalized)
    )


def remove_runtime_error_lines(text: str) -> str:
    kept_lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped and _looks_like_runtime_error_text(stripped):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def normalize_plain_display_symbols(text: str) -> str:
    content = html.unescape(str(text or ""))

    content = re.sub(r"\\[\(\)\[\]]", "", content)
    content = content.replace("$", "")

    def normalize_source_markers(value: str) -> str:
        value = re.sub(
            r"\[\s*FILE\s*_?\s*SOURCE\s*_?\s*(\d+)\s*\]",
            lambda match: f"[FILE_SOURCE_{match.group(1)}]",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\[\s*SOURCE\s*_?\s*(\d+)\s*\]",
            lambda match: f"[SOURCE_{match.group(1)}]",
            value,
            flags=re.IGNORECASE,
        )
        return value

    def join_plain_subscript(match: re.Match) -> str:
        prefix = match.group(1)
        if prefix.upper() == "SOURCE":
            return match.group(0)
        return f"{prefix}{match.group(2)}"

    content = normalize_source_markers(content)

    previous = None
    while previous != content:
        previous = content
        content = re.sub(r"\\(?:text|mathrm)\{([^{}]*)\}", r"\1", content)

    content = content.replace("\\mu", "µ")
    content = re.sub(r"µ\s+g", "µg", content)

    content = re.sub(
        r"\b([A-Za-zÀ-Ỹà-ỹµ]+)_\{([^{}]+)\}",
        join_plain_subscript,
        content,
    )
    content = re.sub(
        r"\b([A-Za-zÀ-Ỹà-ỹµ]+)_([0-9]+(?:,[0-9]+)?)\b",
        join_plain_subscript,
        content,
    )
    content = re.sub(r"\bNm\^\{?3\}?", "Nm3", content)
    content = re.sub(r"\b([mc]?g/Nm)\^\{?3\}?", r"\g<1>3", content)
    content = re.sub(r"\{([^{}\n]+)\}", r"\1", content)
    content = re.sub(r"\\(?=[A-Za-zÀ-Ỹà-ỹµ])", "", content)
    content = re.sub(r"\\+", "", content)
    content = re.sub(r"\bCăn cứ theo\s+về\b", "Căn cứ theo", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*/\s*", "/", content)
    content = re.sub(r"\s+([,.;:!?])", r"\1", content)
    content = normalize_source_markers(content)

    return content


def normalize_display_answer(text: str) -> str:
    cleaned = normalize_plain_display_symbols(
        remove_runtime_error_lines(strip_model_thought_blocks(text))
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    normalized_lines: list[str] = []
    previous_blank = False

    for line in lines:
        if not line:
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip()


def _text_with_file_sections_are_empty_or_error(answer: str) -> bool:
    lowered = _compact_text(answer).lower()
    empty_or_error_markers = (
        "không có dữ liệu",
        "không có kết quả",
        "chưa có kết luận do lỗi",
        "lỗi hệ thống",
        "nội dung file bị lỗi",
        "error code",
        "internal error",
    )
    if any(marker in lowered for marker in empty_or_error_markers):
        return True

    required_headings = (
        "**kết luận**",
        "**dữ liệu trong file**",
        "**căn cứ đối chiếu**",
        "**nhận xét**",
    )
    if not all(heading in lowered for heading in required_headings):
        return False

    for heading in required_headings[1:]:
        pattern = rf"{re.escape(heading)}\s*(?:\*\*|$)"
        if re.search(pattern, lowered):
            return True

    weak_bullets = (
        "- chưa đủ căn cứ. **dữ liệu trong file** - chưa đủ căn cứ.",
        "- chưa đủ căn cứ. **căn cứ đối chiếu** - chưa đủ căn cứ.",
        "- chưa đủ căn cứ. **nhận xét** - chưa đủ căn cứ.",
    )
    return any(marker in lowered for marker in weak_bullets)


def _has_complete_text_with_file_form(answer: str) -> bool:
    lowered = str(answer or "").lower()
    headings = (
        "**kết luận**",
        "**dữ liệu trong file**",
        "**căn cứ đối chiếu**",
        "**nhận xét**",
    )
    if not all(heading in lowered for heading in headings):
        return False
    for index, heading in enumerate(headings):
        start = lowered.find(heading)
        end = lowered.find(headings[index + 1], start + len(heading)) if index + 1 < len(headings) else len(lowered)
        section = lowered[start + len(heading) : end]
        if not re.search(r"(?m)^\s*-\s+\S", section):
            return False
    return True


def is_unusable_text_with_file_answer(answer: str) -> bool:
    compacted = _compact_text(answer)
    lowered = compacted.lower()
    if _has_complete_text_with_file_form(answer) and not looks_like_workflow_runtime_error_text(compacted):
        return _text_with_file_sections_are_empty_or_error(compacted) or _looks_like_raw_router_output(compacted)
    return (
        not compacted
        or lowered in {"none", "null"}
        or compacted == TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK
        or lowered.startswith("chưa tìm thấy căn cứ")
        or lowered.startswith("chưa đủ căn cứ")
        or lowered.startswith("**kết luận** - chưa đủ căn cứ")
        or lowered.startswith("chưa xác định được yêu cầu")
        or _text_with_file_sections_are_empty_or_error(compacted)
        or _looks_like_raw_router_output(compacted)
        or looks_like_workflow_runtime_error_text(compacted)
    )


def is_valid_text_with_file_router_label(router_label: str) -> bool:
    return _compact_text(router_label).upper() in VALID_TEXT_WITH_FILE_ROUTER_LABELS


def recover_text_only_router_label(router_output: str) -> str:
    compacted = _compact_text(router_output).upper()
    if _is_valid_router_label(compacted):
        return compacted

    primary_label_match = re.search(
        r"(?:</THOUGHT>\s*)?PRIMARY_LABEL\s*=\s*([A-Z_]+)",
        compacted,
    )
    if primary_label_match:
        candidate = primary_label_match.group(1)
        return candidate if _is_valid_router_label(candidate) else ""

    final_label_match = re.search(
        r"(?:</THOUGHT>\s*)?FINAL_LABEL\s*=\s*([A-Z_]+)",
        compacted,
    )
    if final_label_match:
        candidate = final_label_match.group(1)
        return candidate if _is_valid_router_label(candidate) else ""

    matches = {
        label
        for label in TEXT_ONLY_ROUTER_LABELS
        if re.search(rf"(?<![A-Z0-9_]){re.escape(label)}(?![A-Z0-9_])", compacted)
    }
    return next(iter(matches)) if len(matches) == 1 else ""


def finalize_comfyui_response(
    *,
    router_output: str,
    raw_answer: str,
    retrieved_chunks: list[dict],
) -> tuple[str, list[dict]]:
    router_label = recover_text_only_router_label(router_output)
    if router_label == "XA_GIAO":
        return GREETING_ANSWER, []
    if router_label == "KHONG_LIEN_QUAN":
        return UNRELATED_ANSWER, []
    return raw_answer, retrieved_chunks


def sanitize_final_response(
    *,
    input_type: str,
    router_output: str,
    final_answer: str,
    retrieved_chunks: list[dict],
) -> tuple[str, str, list[dict]]:
    compact_router = _compact_text(router_output)
    display_answer = normalize_display_answer(final_answer)
    answer_for_validation = _compact_text(display_answer)

    if input_type == "text_with_file":
        router_valid = is_valid_text_with_file_router_label(compact_router)
        if not answer_for_validation or is_unusable_text_with_file_answer(answer_for_validation):
            return TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK, "", []
        if (compact_router and not router_valid) or _looks_like_raw_router_output(
            answer_for_validation
        ):
            return TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK, "", []
        return display_answer, compact_router, retrieved_chunks

    recovered_router = recover_text_only_router_label(compact_router)
    router_valid = bool(recovered_router)
    if compact_router and not router_valid and _looks_like_runtime_error_text(compact_router):
        if not _is_unusable_text_only_answer(answer_for_validation):
            return display_answer, "", retrieved_chunks
        return TEXT_ONLY_INVALID_OUTPUT_FALLBACK, "", []

    if _looks_like_raw_router_output(answer_for_validation):
        return TEXT_ONLY_INVALID_OUTPUT_FALLBACK, "", []
    if compact_router and not router_valid:
        if not _is_unusable_text_only_answer(answer_for_validation):
            return display_answer, "", retrieved_chunks
        return TEXT_ONLY_INVALID_OUTPUT_FALLBACK, "", []
    if not answer_for_validation:
        return TEXT_ONLY_INVALID_OUTPUT_FALLBACK, "", []
    return display_answer, recovered_router, retrieved_chunks


def text_with_file_content_identity(
    *,
    input_result: dict,
    active_document: dict | None,
    file_id: str,
) -> str:
    file_content = _compact_text(input_result.get("file_content", ""))
    if file_content:
        digest = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
        return f"content:{digest}"

    for candidate in (
        (active_document or {}).get("file_hash", ""),
        file_id,
    ):
        compacted = _compact_text(candidate)
        if compacted:
            return f"file:{compacted}"
    return ""


def build_text_with_file_cache_key(
    *,
    question: str,
    mode: str,
    kb_version: str,
    file_identity: str,
) -> str:
    compact_question = _compact_text(question).lower()
    compact_mode = _compact_text(mode).upper()
    compact_kb_version = _compact_text(kb_version)
    compact_file_identity = _compact_text(file_identity)
    if not compact_question or not compact_mode or not compact_file_identity:
        return ""
    return "|".join(
        (
            "text_with_file",
            "v1",
            compact_kb_version,
            compact_mode,
            compact_file_identity,
            compact_question,
        )
    )


def should_cache_text_with_file_answer(final_answer: str, router_label: str) -> bool:
    return is_valid_text_with_file_router_label(
        router_label
    ) and not is_unusable_text_with_file_answer(final_answer)
