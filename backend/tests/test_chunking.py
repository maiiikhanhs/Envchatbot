from app.preprocessing.chunking import chunk_file_content


def test_short_content_creates_one_chunk():
    content = "Quan trắc môi trường là quá trình theo dõi các thông số chất lượng môi trường."

    result = chunk_file_content("Khái niệm là gì?", content)

    assert result["status"] == "success"
    assert result["chunk_count"] == 1
    assert len(result["chunks"]) == 1


def test_long_content_creates_multiple_chunks():
    paragraph = (
        "Thông số COD phản ánh nhu cầu oxy hóa học trong nước. "
        "Giá trị này được sử dụng để đánh giá mức độ ô nhiễm hữu cơ. "
    )
    content = (paragraph * 20).strip()

    result = chunk_file_content("Giải thích nội dung", content)

    assert result["status"] == "success"
    assert result["chunk_count"] > 1


def test_chunks_are_not_empty():
    content = "Dữ liệu quan trắc nước mặt cần được kiểm tra định kỳ.\n\nMẫu phải được bảo quản đúng quy định."

    result = chunk_file_content("Tóm tắt", content)

    assert result["status"] == "success"
    assert all(chunk["content"].strip() for chunk in result["chunks"])


def test_chunks_preserve_content_order():
    content = "Phần một nói về COD.\n\nPhần hai nói về BOD.\n\nPhần ba nói về TSS."

    result = chunk_file_content("Đọc file", content)
    combined = "\n\n".join(chunk["content"] for chunk in result["chunks"])

    assert combined.find("Phần một") < combined.find("Phần hai") < combined.find("Phần ba")


def test_long_block_is_split_reasonably():
    sentence = "COD là chỉ số quan trọng để đánh giá ô nhiễm nước."
    content = " ".join([sentence for _ in range(80)])

    result = chunk_file_content("Phân tích", content)

    assert result["status"] == "success"
    assert result["chunk_count"] > 1
    assert all(chunk["char_count"] <= 1000 for chunk in result["chunks"])


def test_empty_file_content_returns_error():
    result = chunk_file_content("Câu hỏi", "")

    assert result["status"] == "error"
    assert result["error_code"] == "EMPTY_FILE_CONTENT"
    assert result["chunks"] == []


def test_whitespace_file_content_returns_error():
    result = chunk_file_content("Câu hỏi", "   \n   ")

    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_FILE_CONTENT"
    assert result["chunks"] == []
