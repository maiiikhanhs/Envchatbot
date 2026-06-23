"""Authentication service — register & login with MongoDB users collection."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.database.mongo import get_collection

USERS_COLLECTION = "users"


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash (sufficient for a demo/thesis project)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_users_indexes() -> None:
    """Create unique index on username."""
    col = get_collection(USERS_COLLECTION)
    col.create_index("username", unique=True)


def register_user(username: str, password: str) -> dict:
    """
    Register a new user.

    Returns dict with keys: status, message, user (on success).
    Raises ValueError on validation failure.
    """
    # ── Validation ──
    username = username.strip().lower()

    if len(username) < 3:
        return {"status": "error", "message": "Tên tài khoản phải có ít nhất 3 ký tự"}

    if len(username) > 30:
        return {"status": "error", "message": "Tên tài khoản không được quá 30 ký tự"}

    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return {
            "status": "error",
            "message": "Tên tài khoản chỉ được chứa chữ cái, số và dấu gạch dưới",
        }

    if len(password) < 6:
        return {"status": "error", "message": "Mật khẩu phải có ít nhất 6 ký tự"}

    # ── Insert into MongoDB ──
    now = _utc_now_iso()
    user_doc = {
        "username": username,
        "password_hash": _hash_password(password),
        "display_name": username.capitalize(),
        "role": "user",
        "created_at": now,
        "updated_at": now,
    }

    try:
        col = get_collection(USERS_COLLECTION)
        result = col.insert_one(user_doc)
        return {
            "status": "success",
            "message": "Đăng ký thành công",
            "user": {
                "id": str(result.inserted_id),
                "username": username,
                "display_name": user_doc["display_name"],
            },
        }
    except DuplicateKeyError:
        return {"status": "error", "message": "Tên tài khoản đã tồn tại"}


def login_user(username: str, password: str) -> dict:
    """
    Authenticate a user.

    Returns dict with keys: status, message, user (on success).
    """
    username = username.strip().lower()
    password_hash = _hash_password(password)

    col = get_collection(USERS_COLLECTION)
    user_doc = col.find_one({"username": username, "password_hash": password_hash})

    if not user_doc:
        return {"status": "error", "message": "Tên đăng nhập hoặc mật khẩu không đúng"}

    return {
        "status": "success",
        "message": "Đăng nhập thành công",
        "user": {
            "id": str(user_doc["_id"]),
            "username": user_doc["username"],
            "display_name": user_doc.get("display_name", user_doc["username"]),
        },
    }


def seed_default_users() -> None:
    """Create default admin/user accounts if they don't exist yet."""
    col = get_collection(USERS_COLLECTION)

    defaults = [
        {"username": "admin", "password": "admin123", "display_name": "Admin", "role": "admin"},
        {"username": "user", "password": "user123", "display_name": "User", "role": "user"},
    ]

    for acct in defaults:
        if not col.find_one({"username": acct["username"]}):
            now = _utc_now_iso()
            col.insert_one(
                {
                    "username": acct["username"],
                    "password_hash": _hash_password(acct["password"]),
                    "display_name": acct["display_name"],
                    "role": acct["role"],
                    "created_at": now,
                    "updated_at": now,
                }
            )
