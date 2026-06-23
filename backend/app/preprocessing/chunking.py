from __future__ import annotations
"""Chunk file content into clean segments for ComfyUI preprocessing."""

import re
import uuid


ERROR_EMPTY_FILE_CONTENT = "EMPTY_FILE_CONTENT"
ERROR_INVALID_FILE_CONTENT = "INVALID_FILE_CONTENT"


def validate_file_content(file_content):
    """Validate extracted file content before chunking."""
    if file_content is None or file_content == "":
        return False, ERROR_EMPTY_FILE_CONTENT

    if not str(file_content).strip():
        return False, ERROR_INVALID_FILE_CONTENT

    return True, None


def normalize_text_for_chunking(file_content):
    """Normalize whitespace and line breaks before block splitting."""
    text = str(file_content).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_blocks(text):
    """Split text into logical blocks using blank lines."""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return blocks


def split_long_block_into_sentences(block):
    """Split oversized blocks into smaller sentence-like units."""
    normalized_block = re.sub(r"\s+", " ", block).strip()
    if not normalized_block:
        return []

    parts = re.split(r"(?<=[\.\!\?;])\s+", normalized_block)
    sentences = [part.strip() for part in parts if part.strip()]

    if not sentences:
        return [normalized_block]

    return sentences


def build_chunks(blocks, max_chars_per_chunk=1000, min_chars_per_chunk=250):
    """Build ordered chunks suitable for downstream retrieval and workflow input."""
    units = []

    for block in blocks:
        if len(block) > max_chars_per_chunk:
            units.extend(split_long_block_into_sentences(block))
        else:
            units.append(block)

    chunks = []
    current_chunk = ""

    for unit in units:
        if not unit:
            continue

        separator = "\n\n" if current_chunk else ""
        candidate = f"{current_chunk}{separator}{unit}" if current_chunk else unit

        if len(candidate) <= max_chars_per_chunk:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)

        if len(unit) <= max_chars_per_chunk:
            current_chunk = unit
            continue

        start = 0
        while start < len(unit):
            end = min(start + max_chars_per_chunk, len(unit))
            piece = unit[start:end].strip()
            if piece:
                chunks.append(piece)
            start = end
        current_chunk = ""

    if current_chunk:
        chunks.append(current_chunk)

    if len(chunks) > 1 and len(chunks[-1]) < min_chars_per_chunk:
        candidate = f"{chunks[-2]}\n\n{chunks[-1]}"
        if len(candidate) <= max_chars_per_chunk:
            chunks[-2] = candidate
            chunks.pop()

    return chunks


def create_chunk_object(content, chunk_index, file_info=None):
    """Attach lightweight metadata required by later preprocessing steps."""
    safe_file_info = file_info or {}

    return {
        "chunk_id": f"{uuid.uuid4().hex[:12]}_chunk_{chunk_index}",
        "content": content,
        "chunk_index": chunk_index,
        "char_count": len(content),
        "word_count": len(content.split()),
        "source_file_name": safe_file_info.get("file_name"),
        "source_file_extension": safe_file_info.get("file_extension"),
    }


def build_success_response(question, file_info, chunks):
    """Return chunking output for later embedding/retrieval."""
    return {
        "status": "success",
        "question": question,
        "file_info": file_info,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def build_error_response(error_code, error_message):
    """Return a stable error payload for chunking."""
    return {
        "status": "error",
        "error_code": error_code,
        "error_message": error_message,
        "chunks": [],
    }


def chunk_file_content(question: str, file_content: str, file_info: dict | None = None) -> dict:
    """Convert extracted file content into ordered chunks for ComfyUI preprocessing."""
    is_valid, error_code = validate_file_content(file_content)
    if not is_valid:
        return build_error_response(error_code, error_code)

    normalized_text = normalize_text_for_chunking(file_content)
    blocks = split_into_blocks(normalized_text)
    raw_chunks = build_chunks(blocks)
    chunks = [
        create_chunk_object(content=chunk, chunk_index=index, file_info=file_info)
        for index, chunk in enumerate(raw_chunks, start=1)
    ]

    return build_success_response(question=question, file_info=file_info, chunks=chunks)
