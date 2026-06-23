from pathlib import Path

from docx import Document

from app.input.input_processor import prepare_chatbot_input
from app.models.schemas import (
    ERROR_FILE_ONLY_NOT_ALLOWED,
    ERROR_MISSING_QUESTION,
    ERROR_UNSUPPORTED_FILE_TYPE,
    INPUT_TYPE_INVALID,
    INPUT_TYPE_TEXT_ONLY,
    INPUT_TYPE_TEXT_WITH_FILE,
)


def create_sample_docx(file_path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(file_path)


def test_text_only_success():
    result = prepare_chatbot_input("  Cho tôi biết chỉ số COD là gì?   ")

    assert result["status"] == "success"
    assert result["input_type"] == INPUT_TYPE_TEXT_ONLY
    assert result["user_question"] == "  Cho tôi biết chỉ số COD là gì?   "
    assert result["normalized_question"] == "Cho tôi biết chỉ số COD là gì?"
    assert result["has_file"] is False
    assert result["file_info"] is None
    assert result["file_content"] == ""
    assert result["prepared_context"]["question"] == "Cho tôi biết chỉ số COD là gì?"
    assert result["prepared_context"]["file_content"] == ""
    assert result["prepared_context"]["combined_context"] == "Cho tôi biết chỉ số COD là gì?"
    assert result["error_code"] is None
    assert result["error_message"] is None


def test_text_with_docx_success(tmp_path: Path):
    file_path = tmp_path / "sample.docx"
    create_sample_docx(file_path, "COD là nhu cầu oxy hóa học.")

    result = prepare_chatbot_input("Giải thích nội dung tài liệu", str(file_path))

    assert result["status"] == "success"
    assert result["input_type"] == INPUT_TYPE_TEXT_WITH_FILE
    assert result["has_file"] is True
    assert result["file_info"]["file_name"] == "sample.docx"
    assert result["file_info"]["file_extension"] == ".docx"
    assert "COD là nhu cầu oxy hóa học." in result["file_content"]
    assert result["prepared_context"]["question"] == "Giải thích nội dung tài liệu"
    assert result["prepared_context"]["file_content"] == result["file_content"]
    assert "Question: Giải thích nội dung tài liệu" in result["prepared_context"]["combined_context"]


def test_missing_question():
    result = prepare_chatbot_input("   ")

    assert result["status"] == "error"
    assert result["input_type"] == INPUT_TYPE_INVALID
    assert result["error_code"] == ERROR_MISSING_QUESTION
    assert result["error_message"] == ERROR_MISSING_QUESTION


def test_unsupported_file_type(tmp_path: Path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("du lieu", encoding="utf-8")

    result = prepare_chatbot_input("Đọc file này", str(file_path))

    assert result["status"] == "error"
    assert result["input_type"] == INPUT_TYPE_INVALID
    assert result["has_file"] is True
    assert result["error_code"] == ERROR_UNSUPPORTED_FILE_TYPE


def test_file_only_not_allowed(tmp_path: Path):
    file_path = tmp_path / "sample.docx"
    create_sample_docx(file_path, "Noi dung")

    result = prepare_chatbot_input("   ", str(file_path))

    assert result["status"] == "error"
    assert result["input_type"] == INPUT_TYPE_INVALID
    assert result["has_file"] is True
    assert result["error_code"] == ERROR_FILE_ONLY_NOT_ALLOWED
