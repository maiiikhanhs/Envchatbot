from app.retrieval.embedding import (
    embed_chunks,
    generate_mock_embedding,
)


def sample_chunks():
    return [
        {
            "chunk_id": "chunk_1",
            "content": "COD là chỉ số đánh giá ô nhiễm hữu cơ trong nước.",
            "chunk_index": 1,
        },
        {
            "chunk_id": "chunk_2",
            "content": "BOD phản ánh lượng oxy cần cho vi sinh vật phân hủy chất hữu cơ.",
            "chunk_index": 2,
        },
    ]


def test_valid_chunks_return_success():
    result = embed_chunks(sample_chunks())

    assert result["status"] == "success"
    assert result["chunk_count"] == 2
    assert len(result["chunks"]) == 2


def test_embedding_has_correct_dimension():
    vector = generate_mock_embedding("COD", dimension=8)

    assert isinstance(vector, list)
    assert len(vector) == 8
    assert all(isinstance(value, float) for value in vector)


def test_same_text_produces_same_embedding():
    vector_1 = generate_mock_embedding("Thông số COD", dimension=8)
    vector_2 = generate_mock_embedding("Thông số COD", dimension=8)

    assert vector_1 == vector_2


def test_processed_chunk_contains_embedding_field():
    result = embed_chunks(sample_chunks())

    assert "embedding" in result["chunks"][0]
    assert len(result["chunks"][0]["embedding"]) == result["embedding_dimension"]


def test_empty_chunks_return_error():
    result = embed_chunks([])

    assert result["status"] == "error"
    assert result["error_code"] == "EMPTY_CHUNKS"
    assert result["chunks"] == []


def test_invalid_chunk_schema_returns_error():
    invalid_chunks = [{"chunk_id": "chunk_1", "chunk_index": 1}]

    result = embed_chunks(invalid_chunks)

    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_CHUNKS"
    assert result["chunks"] == []
