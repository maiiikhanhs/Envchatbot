from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfWriter

from app.input.file_reader import (
    extract_file_content,
    FileNotFoundCustomError,
    UnsupportedFileTypeError,
    FileExtractionError,
)


def create_sample_docx(file_path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(file_path)


def create_blank_pdf(file_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with open(file_path, "wb") as f:
        writer.write(f)


def test_extract_docx_text_success(tmp_path: Path):
    file_path = tmp_path / "sample.docx"
    create_sample_docx(file_path, "Thông số COD là gì?")

    file_info, file_content = extract_file_content(str(file_path))

    assert file_info["file_name"] == "sample.docx"
    assert file_info["file_extension"] == ".docx"
    assert "Thông số COD là gì?" in file_content


def test_file_not_found():
    with pytest.raises(FileNotFoundCustomError):
        extract_file_content("not_found.docx")


def test_unsupported_file_type(tmp_path: Path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        extract_file_content(str(file_path))


def test_pdf_extract_fail_with_blank_pdf(tmp_path: Path):
    file_path = tmp_path / "blank.pdf"
    create_blank_pdf(file_path)

    with pytest.raises(FileExtractionError):
        extract_file_content(str(file_path))
