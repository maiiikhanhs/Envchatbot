from __future__ import annotations

TEXT_WITH_FILE_MODE_SUMMARY = "file_summary"
TEXT_WITH_FILE_MODE_QA = "file_qa"
TEXT_WITH_FILE_MODE_VS_KB = "file_vs_kb"
FILE_SUMMARY_MAX_CONTEXT_CHARS = 20000
FILE_QA_MAX_CONTEXT_CHARS = 9000
FILE_VS_KB_MAX_CONTEXT_CHARS = 7000
FILE_QA_BASE_TOP_K = 8
FILE_QA_FOLLOW_UP_TOP_K = 10


from app.services.chat_text_only_service import _compact_text


def _chunk_identity(chunk: dict) -> str:
    return str(chunk.get("chunk_id") or chunk.get("content", ""))


def _deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    deduplicated_chunks: list[dict] = []
    seen_keys: set[str] = set()

    for chunk in chunks:
        key = _chunk_identity(chunk)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated_chunks.append(chunk)

    return deduplicated_chunks


def _build_file_anchor_text(
    *,
    effective_question: str = "",
    final_answer: str = "",
    retrieved_chunks: list[dict] | None = None,
    max_chunk_chars: int = 180,
) -> str:
    parts: list[str] = []

    compact_question = _compact_text(effective_question)
    if compact_question:
        parts.append(compact_question)

    compact_answer = _compact_text(final_answer)
    if compact_answer:
        parts.append(compact_answer)

    seen_chunk_texts: set[str] = set()
    for chunk in retrieved_chunks or []:
        chunk_text = _compact_text(chunk.get("content", ""))
        if not chunk_text or chunk_text in seen_chunk_texts:
            continue
        seen_chunk_texts.add(chunk_text)
        if len(chunk_text) > max_chunk_chars:
            chunk_text = f"{chunk_text[: max_chunk_chars - 3].rstrip()}..."
        parts.append(chunk_text)
        if len(parts) >= 4:
            break

    return " | ".join(parts)

def _normalize_chunk_ids(chunk_ids: list[str] | None) -> list[str]:
    normalized_ids: list[str] = []
    seen_ids: set[str] = set()
    for chunk_id in chunk_ids or []:
        normalized = _compact_text(chunk_id)
        if not normalized or normalized in seen_ids:
            continue
        seen_ids.add(normalized)
        normalized_ids.append(normalized)
    return normalized_ids


def _get_chunks_by_ids(chunks: list[dict], chunk_ids: list[str] | None) -> list[dict]:
    normalized_ids = _normalize_chunk_ids(chunk_ids)
    if not normalized_ids:
        return []

    chunk_map = {
        _compact_text(chunk.get("chunk_id", "")): chunk
        for chunk in chunks
        if _compact_text(chunk.get("chunk_id", ""))
    }
    return [chunk_map[chunk_id] for chunk_id in normalized_ids if chunk_id in chunk_map]

def _build_chunk_documents_from_storage(document: dict, stored_chunks: list[dict], kb_version: str) -> list[dict]:
    document_id = str(document.get("_id", ""))
    built_chunks = []

    for stored_chunk in stored_chunks:
        content = str(stored_chunk.get("content", "")).strip()
        if not content:
            continue

        built_chunks.append(
            {
                "chunk_id": stored_chunk.get("chunk_id", ""),
                "chunk_index": int(stored_chunk.get("chunk_index", 0)),
                "content": content,
                "char_count": int(stored_chunk.get("char_count", len(content))),
                "word_count": int(stored_chunk.get("word_count", len(content.split()))),
                "source_file_name": stored_chunk.get("source_file_name") or document.get("file_name", ""),
                "source_file_extension": stored_chunk.get("source_file_extension") or document.get("file_type", ""),
                "document_id": document_id,
                "category": stored_chunk.get("category") or document.get("category", "general"),
                "kb_version": stored_chunk.get("kb_version", kb_version),
            }
        )

    return built_chunks

def _deduplicate_and_sort_chunks(chunks: list[dict]) -> list[dict]:
    return _deduplicate_chunks(
        sorted(chunks, key=lambda item: int(item.get("chunk_index", 0)))
    )


def _looks_like_heading(content: str) -> bool:
    stripped = str(content or "").strip()
    if not stripped:
        return False
    first_line = stripped.splitlines()[0].strip()
    if not first_line:
        return False
    if len(first_line) <= 120 and first_line == first_line.upper():
        return True
    heading_markers = (
        "mục ",
        "phần ",
        "chương ",
        "điều ",
        "khoản ",
        "phụ lục",
        "kết luận",
        "mở đầu",
        "giới thiệu",
    )
    lowered = first_line.lower()
    return any(lowered.startswith(marker) for marker in heading_markers)


def _select_summary_chunks(chunks: list[dict]) -> list[dict]:
    ordered_chunks = _deduplicate_and_sort_chunks(chunks)
    if not ordered_chunks:
        return []

    selected: list[dict] = []
    seen_keys: set[str] = set()

    def add_chunk(chunk: dict) -> None:
        key = _chunk_identity(chunk)
        if key in seen_keys:
            return
        seen_keys.add(key)
        selected.append(chunk)

    add_chunk(ordered_chunks[0])

    for chunk in ordered_chunks[1:]:
        if _looks_like_heading(chunk.get("content", "")):
            add_chunk(chunk)

    for chunk in ordered_chunks[1:]:
        add_chunk(chunk)

    return selected

def _build_context_from_chunks(
    *,
    question: str,
    chunks: list[dict],
    max_context_chars: int,
    section_title: str,
    source_label_prefix: str = "SOURCE",
    preserve_input_order: bool = False,
) -> tuple[str, list[dict]]:
    if preserve_input_order:
        ordered_chunks = _deduplicate_chunks(chunks)
    else:
        ordered_chunks = _deduplicate_and_sort_chunks(chunks)
    header = f"Question: {question.strip()}\n\n{section_title}:\n"
    current_context = header
    selected_chunks: list[dict] = []

    for index, chunk in enumerate(ordered_chunks, start=1):
        source_file = chunk.get("source_file_name", "Tài liệu upload")
        chunk_text = (
            f"[{source_label_prefix}_{index}] (Nguồn: {source_file}): "
            f"{str(chunk.get('content', '')).strip()}\n\n"
        )

        if len(current_context) + len(chunk_text) > max_context_chars:
            break

        current_context += chunk_text
        selected_chunks.append(chunk)

    return current_context.strip(), selected_chunks


def _build_file_summary_context(
    *,
    question: str,
    chunks: list[dict],
    max_context_chars: int = FILE_SUMMARY_MAX_CONTEXT_CHARS,
) -> tuple[str, list[dict]]:
    return _build_context_from_chunks(
        question=question,
        chunks=_select_summary_chunks(chunks),
        max_context_chars=max_context_chars,
        section_title="File Content",
        source_label_prefix="FILE_SOURCE",
        preserve_input_order=True,
    )


def _build_file_vs_kb_context(
    *,
    question: str,
    chunks: list[dict],
    max_context_chars: int = FILE_VS_KB_MAX_CONTEXT_CHARS,
) -> tuple[str, list[dict]]:
    file_context, selected_chunks = _build_context_from_chunks(
        question=question,
        chunks=chunks,
        max_context_chars=max_context_chars,
        section_title="Relevant Context",
        source_label_prefix="FILE_SOURCE",
    )
    prefixed_context = f"=== FILE UPLOAD ===\n\n{file_context}"
    return prefixed_context.strip(), selected_chunks


def _merge_chunks(*chunk_lists: list[dict]) -> list[dict]:
    return _deduplicate_chunks(
        [chunk for chunk_list in chunk_lists for chunk in chunk_list]
    )
