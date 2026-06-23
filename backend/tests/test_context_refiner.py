from app.workflow.context_refiner import refine_context


def sample_chunks():
    return [
        {
            "chunk_id": "chunk_3",
            "content": "TSS là tổng chất rắn lơ lửng trong nước.",
            "chunk_index": 3,
            "similarity_score": 0.8,
        },
        {
            "chunk_id": "chunk_1",
            "content": "COD là chỉ số đánh giá ô nhiễm hữu cơ trong nước.",
            "chunk_index": 1,
            "similarity_score": 0.95,
        },
        {
            "chunk_id": "chunk_2",
            "content": "BOD phản ánh lượng oxy cần cho vi sinh vật phân hủy chất hữu cơ.",
            "chunk_index": 2,
            "similarity_score": 0.9,
        },
    ]


def test_refine_context_success_with_valid_chunks():
    result = refine_context("COD là gì?", sample_chunks())

    assert result["status"] == "success"
    assert result["chunk_count"] == 3
    assert result["refined_context"]


def test_deduplicate_chunks_by_content():
    chunks = sample_chunks() + [
        {
            "chunk_id": "chunk_4",
            "content": "COD là chỉ số đánh giá ô nhiễm hữu cơ trong nước.",
            "chunk_index": 4,
            "similarity_score": 0.7,
        }
    ]

    result = refine_context("COD là gì?", chunks)

    assert result["status"] == "success"
    assert result["chunk_count"] == 3


def test_keep_order_by_chunk_index():
    result = refine_context("Thông số nước", sample_chunks())

    chunk_indexes = [chunk["chunk_index"] for chunk in result["chunks"]]
    assert chunk_indexes == [1, 2, 3]


def test_refined_context_contains_question():
    result = refine_context("COD là gì?", sample_chunks())

    assert "Question: COD là gì?" in result["refined_context"]


def test_refined_context_supports_file_source_prefix_and_section_title():
    result = refine_context(
        "COD là gì?",
        sample_chunks(),
        max_context_chars=1000,
        section_title="File Context",
        source_label_prefix="FILE_SOURCE",
    )

    assert "File Context:" in result["refined_context"]
    assert "[FILE_SOURCE_1]" in result["refined_context"]


def test_refined_context_respects_max_context_chars():
    large_chunks = [
        {
            "chunk_id": "chunk_1",
            "content": "A" * 200,
            "chunk_index": 1,
        },
        {
            "chunk_id": "chunk_2",
            "content": "B" * 200,
            "chunk_index": 2,
        },
        {
            "chunk_id": "chunk_3",
            "content": "C" * 200,
            "chunk_index": 3,
        },
    ]

    result = refine_context("Giới hạn context", large_chunks, max_context_chars=260)

    assert result["status"] == "success"
    assert len(result["refined_context"]) <= 260


def test_empty_question_returns_error():
    result = refine_context("   ", sample_chunks())

    assert result["status"] == "error"
    assert result["error_code"] == "MISSING_QUESTION"


def test_empty_chunks_returns_error():
    result = refine_context("COD là gì?", [])

    assert result["status"] == "error"
    assert result["error_code"] == "EMPTY_CHUNKS"


def test_missing_required_chunk_field_returns_error():
    invalid_chunks = [{"chunk_id": "chunk_1", "content": "COD"}]

    result = refine_context("COD là gì?", invalid_chunks)

    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_RETRIEVED_CHUNKS"
