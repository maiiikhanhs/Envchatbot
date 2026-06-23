from __future__ import annotations
"""Chunk embedding step for preprocessing-time retrieval before ComfyUI."""

import hashlib


ERROR_EMPTY_CHUNKS = "EMPTY_CHUNKS"
ERROR_INVALID_CHUNKS = "INVALID_CHUNKS"


def validate_chunks(chunks):
    """Validate chunk objects before attaching retrieval embeddings."""
    if not isinstance(chunks, list) or len(chunks) == 0:
        return False, ERROR_EMPTY_CHUNKS

    for chunk in chunks:
        if not isinstance(chunk, dict):
            return False, ERROR_INVALID_CHUNKS

        if "chunk_id" not in chunk or "content" not in chunk or "chunk_index" not in chunk:
            return False, ERROR_INVALID_CHUNKS

        if not isinstance(chunk["content"], str) or not chunk["content"].strip():
            return False, ERROR_INVALID_CHUNKS

    return True, None


_embedding_model = None

def get_embedding_model():
    """Lazy load the sentence-transformer model to avoid blocking startup."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # Su dung dung model ma ComfyUI dang dung de dbong bo
        _embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


def generate_mock_embedding(text, dimension=384):
    """(DEPRECATED) Generate a deterministic lightweight embedding."""
    normalized_text = str(text)
    values = []
    import hashlib
    for index in range(dimension):
        digest = hashlib.sha256(f"{index}:{normalized_text}".encode("utf-8")).digest()
        integer_value = int.from_bytes(digest[:8], "big")
        scaled_value = round(integer_value / float(2**64 - 1), 6)
        values.append(scaled_value)
    return values


def generate_real_embedding(text):
    """Generate a real semantic embedding using sentence-transformers."""
    model = get_embedding_model()
    # Phat sinh list cac float vector
    embedding = model.encode(str(text))
    return embedding.tolist()


def attach_embedding_to_chunk(chunk, dimension=384):
    """Attach an embedding to a single chunk for retrieval preparation."""
    updated_chunk = dict(chunk)
    updated_chunk["embedding"] = generate_real_embedding(chunk["content"])
    return updated_chunk


def build_success_response(embedded_chunks):
    """Return embedded chunks for the retrieval step."""
    embedding_dimension = len(embedded_chunks[0]["embedding"]) if embedded_chunks else 0
    return {
        "status": "success",
        "embedding_dimension": embedding_dimension,
        "chunk_count": len(embedded_chunks),
        "chunks": embedded_chunks,
    }


def build_error_response(error_code, error_message):
    """Return a stable error payload for embedding failures."""
    return {
        "status": "error",
        "error_code": error_code,
        "error_message": error_message,
        "chunks": [],
    }


def embed_chunks(chunks: list[dict]) -> dict:
    """Embed chunks for file-level retrieval inside the preprocessing flow."""
    is_valid, error_code = validate_chunks(chunks)
    if not is_valid:
        return build_error_response(error_code, error_code)

    embedded_chunks = [attach_embedding_to_chunk(chunk) for chunk in chunks]
    return build_success_response(embedded_chunks)
