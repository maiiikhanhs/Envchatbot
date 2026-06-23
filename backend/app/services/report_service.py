from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import UploadFile

from app.config import BACKEND_ROOT
from app.database.mongo import MESSAGES_COLLECTION, REPORTS_COLLECTION, get_collection
from app.models.db_schemas import build_report_record, utc_now_iso

REPORT_TYPES = {"bug", "suggestion", "feature"}
REPORT_STATUSES = {"new", "reviewing", "resolved", "dismissed"}
REPORT_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg"}
REPORT_MIN_CONTENT_LENGTH = 20
REPORT_MAX_CONTENT_LENGTH = 1000
REPORT_MAX_FILE_BYTES = 5 * 1024 * 1024
REPORT_UPLOAD_DIR = BACKEND_ROOT / "uploads" / "reports"


class ReportValidationError(ValueError):
    pass


def _safe_object_id(value: str):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _parse_client_context(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReportValidationError("client_context phải là JSON hợp lệ") from exc
    return parsed if isinstance(parsed, dict) else {}


def _validate_report_type(report_type: str) -> str:
    value = str(report_type or "").strip()
    if value not in REPORT_TYPES:
        raise ReportValidationError("Loại phản hồi không hợp lệ")
    return value


def _validate_content(content: str) -> str:
    value = re.sub(r"\s+", " ", str(content or "")).strip()
    if len(value) < REPORT_MIN_CONTENT_LENGTH:
        raise ReportValidationError("Mô tả phải có ít nhất 20 ký tự")
    if len(value) > REPORT_MAX_CONTENT_LENGTH:
        raise ReportValidationError("Mô tả không được vượt quá 1000 ký tự")
    return value


def _message_snapshot(message_id: str) -> dict:
    object_id = _safe_object_id(message_id)
    if object_id is None:
        return {}
    message = get_collection(MESSAGES_COLLECTION).find_one({"_id": object_id}) or {}
    return {
        "question": message.get("question", ""),
        "answer": message.get("answer", ""),
        "input_type": message.get("input_type", ""),
        "file_id": message.get("file_id"),
        "router_label": message.get("router_label", ""),
        "retrieved_chunk_ids": list(message.get("retrieved_chunk_ids") or []),
    } if message else {}


def _save_attachment(attachment: UploadFile | None) -> dict:
    if not attachment or not attachment.filename:
        return {}

    suffix = REPORT_IMAGE_TYPES.get(str(attachment.content_type or "").lower())
    if suffix is None:
        raise ReportValidationError("Chỉ hỗ trợ ảnh PNG hoặc JPG")

    content = attachment.file.read()
    if len(content) > REPORT_MAX_FILE_BYTES:
        raise ReportValidationError("Kích thước tệp vượt quá 5MB")

    REPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_original = Path(attachment.filename).name
    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = REPORT_UPLOAD_DIR / stored_name
    stored_path.write_bytes(content)

    return {
        "original_file_name": safe_original,
        "file_name": stored_name,
        "file_path": str(stored_path),
        "content_type": attachment.content_type,
        "size_bytes": len(content),
    }


def create_report(
    *,
    report_type: str,
    content: str,
    user_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
    client_context: str | None = None,
    attachment: UploadFile | None = None,
) -> dict:
    record = build_report_record(
        user_id=str(user_id or "").strip(),
        conversation_id=str(conversation_id or "").strip(),
        message_id=str(message_id or "").strip(),
        report_type=_validate_report_type(report_type),
        content=_validate_content(content),
        client_context=_parse_client_context(client_context),
        message_snapshot=_message_snapshot(message_id),
        attachment=_save_attachment(attachment),
    )
    result = get_collection(REPORTS_COLLECTION).insert_one(record)
    return {"status": "success", "report_id": str(result.inserted_id), "message": "Cảm ơn bạn đã gửi phản hồi."}


def list_reports(*, status: str = "", report_type: str = "", limit: int = 50, skip: int = 0) -> list[dict]:
    query = {}
    if status:
        query["status"] = status
    if report_type:
        query["report_type"] = report_type
    cursor = (
        get_collection(REPORTS_COLLECTION)
        .find(query)
        .sort("created_at", -1)
        .skip(max(0, skip))
        .limit(min(max(1, limit), 100))
    )
    reports = []
    for item in cursor:
        item["_id"] = str(item["_id"])
        reports.append(item)
    return reports


def update_report_status(report_id: str, status: str, note: str = "") -> dict:
    if status not in REPORT_STATUSES:
        raise ReportValidationError("Trạng thái report không hợp lệ")
    object_id = _safe_object_id(report_id)
    if object_id is None:
        return {"status": "error", "message": "Report không tồn tại"}

    update = {"status": status, "updated_at": utc_now_iso()}
    if note.strip():
        update["resolution_note"] = note.strip()
    result = get_collection(REPORTS_COLLECTION).update_one({"_id": object_id}, {"$set": update})
    if result.matched_count == 0:
        return {"status": "error", "message": "Report không tồn tại"}
    return {"status": "success", "report_id": report_id}
