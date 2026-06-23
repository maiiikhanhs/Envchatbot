from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from app.database.mongo import MESSAGES_COLLECTION, REPORTS_COLLECTION
from app.services import report_service


class FakeCollection:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.inserted = []
        self.updated = []

    def find_one(self, query):
        target_id = query.get("_id")
        return next((item for item in self.items if item.get("_id") == target_id), None)

    def insert_one(self, record):
        self.inserted.append(record)
        return SimpleNamespace(inserted_id="report-1")

    def update_one(self, query, update):
        self.updated.append((query, update))
        return SimpleNamespace(matched_count=1)

    def find(self, query):
        return FakeCursor(self.items)


class FakeCursor:
    def __init__(self, items):
        self.items = list(items)

    def sort(self, *_):
        return self

    def skip(self, value):
        self.items = self.items[value:]
        return self

    def limit(self, value):
        self.items = self.items[:value]
        return self

    def __iter__(self):
        return iter(self.items)


def fake_upload(name="shot.png", content_type="image/png", content=b"png"):
    return SimpleNamespace(filename=name, content_type=content_type, file=BytesIO(content))


def test_create_report_without_attachment(monkeypatch):
    reports = FakeCollection()

    def fake_get_collection(name):
        return reports if name == REPORTS_COLLECTION else FakeCollection()

    monkeypatch.setattr(report_service, "get_collection", fake_get_collection)

    result = report_service.create_report(
        report_type="bug",
        content="Câu trả lời đang hiển thị sai số liệu trong bảng.",
        user_id="tester",
    )

    assert result["status"] == "success"
    assert reports.inserted[0]["report_type"] == "bug"
    assert reports.inserted[0]["user_id"] == "tester"
    assert reports.inserted[0]["attachment"] == {}


def test_create_report_rejects_short_content():
    with pytest.raises(report_service.ReportValidationError):
        report_service.create_report(report_type="bug", content="quá ngắn")


def test_create_report_rejects_invalid_type():
    with pytest.raises(report_service.ReportValidationError):
        report_service.create_report(report_type="other", content="Nội dung đủ dài để validate.")


def test_create_report_saves_valid_attachment(monkeypatch, tmp_path):
    reports = FakeCollection()
    monkeypatch.setattr(report_service, "REPORT_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        report_service,
        "get_collection",
        lambda name: reports if name == REPORTS_COLLECTION else FakeCollection(),
    )

    report_service.create_report(
        report_type="suggestion",
        content="Nên cải thiện phần hiển thị nguồn tham khảo trong câu trả lời.",
        attachment=fake_upload(content=b"image-bytes"),
    )

    attachment = reports.inserted[0]["attachment"]
    assert attachment["content_type"] == "image/png"
    assert attachment["size_bytes"] == len(b"image-bytes")
    assert (tmp_path / attachment["file_name"]).exists()


def test_create_report_rejects_invalid_attachment_type():
    with pytest.raises(report_service.ReportValidationError):
        report_service.create_report(
            report_type="bug",
            content="Ảnh đính kèm đang dùng sai định dạng cần bị từ chối.",
            attachment=fake_upload(name="note.txt", content_type="text/plain"),
        )


def test_update_report_status_rejects_invalid_status():
    with pytest.raises(report_service.ReportValidationError):
        report_service.update_report_status("report-id", "done")
