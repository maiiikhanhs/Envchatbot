from __future__ import annotations
"""Refine retrieved chunks into compact workflow-ready context."""


ERROR_MISSING_QUESTION = "MISSING_QUESTION"
ERROR_EMPTY_CHUNKS = "EMPTY_CHUNKS"
ERROR_INVALID_RETRIEVED_CHUNKS = "INVALID_RETRIEVED_CHUNKS"


def validate_question(question):
    """Validate the question before context refinement."""
    if question is None or not str(question).strip():
        return False, ERROR_MISSING_QUESTION
    return True, None


def validate_retrieved_chunks(chunks):
    """Validate retrieved chunks before building final context."""
    if not isinstance(chunks, list) or len(chunks) == 0:
        return False, ERROR_EMPTY_CHUNKS

    for chunk in chunks:
        if not isinstance(chunk, dict):
            return False, ERROR_INVALID_RETRIEVED_CHUNKS
        if "content" not in chunk or "chunk_index" not in chunk:
            return False, ERROR_INVALID_RETRIEVED_CHUNKS
        if not isinstance(chunk["content"], str) or not chunk["content"].strip():
            return False, ERROR_INVALID_RETRIEVED_CHUNKS

    return True, None


def deduplicate_chunks(chunks):
    """Remove fully duplicated chunk content."""
    seen_contents = set()
    deduplicated = []

    for chunk in chunks:
        content = chunk["content"]
        if content in seen_contents:
            continue
        seen_contents.add(content)
        deduplicated.append(chunk)

    return deduplicated


def sort_chunks_for_context(chunks):
    """Restore document order for final context assembly."""
    return sorted(chunks, key=lambda chunk: chunk["chunk_index"])


def build_combined_context(
    question,
    chunks,
    max_context_chars=6000,
    section_title="Relevant Context",
    source_label_prefix="SOURCE",
):
    """Build a compact context string suitable for ComfyUI workflow input."""
    header = f"Question: {question.strip()}\n\n{section_title}:\n"
    current_context = header
    selected_chunks = []

    for index, chunk in enumerate(chunks):
        source_file = chunk.get("source_file_name", "Tài liệu upload")
        source_id = index + 1
        chunk_text = (
            f"[{source_label_prefix}_{source_id}] (Nguồn: {source_file}): "
            f"{chunk['content'].strip()}\n\n"
        )

        if len(current_context) + len(chunk_text) > max_context_chars:
            break

        current_context += chunk_text
        selected_chunks.append(chunk)

    return current_context.strip(), selected_chunks


def build_success_response(question, refined_chunks, refined_context, max_context_chars):
    """Return refined context for workflow consumption."""
    return {
        "status": "success",
        "question": question,
        "chunk_count": len(refined_chunks),
        "refined_context": refined_context,
        "chunks": refined_chunks,
        "max_context_chars": max_context_chars,
    }


def build_error_response(error_code, error_message):
    """Return a stable error payload for context refinement failures."""
    return {
        "status": "error",
        "error_code": error_code,
        "error_message": error_message,
        "chunks": [],
    }


def refine_context(
    question: str,
    chunks: list[dict],
    max_context_chars: int = 3000,
    section_title: str = "Relevant Context",
    source_label_prefix: str = "SOURCE",
) -> dict:
    """Refine retrieved chunks into workflow-ready context before ComfyUI."""
    is_valid_question, question_error = validate_question(question)
    if not is_valid_question:
        return build_error_response(question_error, question_error)

    is_valid_chunks, chunks_error = validate_retrieved_chunks(chunks)
    if not is_valid_chunks:
        return build_error_response(chunks_error, chunks_error)

    deduplicated_chunks = deduplicate_chunks(chunks)
    sorted_chunks = sort_chunks_for_context(deduplicated_chunks)
    refined_context, refined_chunks = build_combined_context(
        question,
        sorted_chunks,
        max_context_chars=max_context_chars,
        section_title=section_title,
        source_label_prefix=source_label_prefix,
    )

    return build_success_response(
        question=question,
        refined_chunks=refined_chunks,
        refined_context=refined_context,
        max_context_chars=max_context_chars,
    )
