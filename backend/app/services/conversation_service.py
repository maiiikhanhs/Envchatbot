from __future__ import annotations
import re
from datetime import datetime, timezone
from app.database.mongo import (
    CONVERSATIONS_COLLECTION,
    MESSAGES_COLLECTION,
    QA_CACHE_COLLECTION,
    get_collection,
)
from app.models.db_schemas import (
    build_conversation_record,
    build_exact_cache_record,
    build_message_record,
    utc_now_iso,
)


def get_conversation_by_session(session_id: str) -> dict | None:
    return get_collection(CONVERSATIONS_COLLECTION).find_one({"session_id": session_id})


def _safe_object_id(value: str):
    from bson import ObjectId

    try:
        return ObjectId(value)
    except Exception:
        return None


def get_conversation_by_id(conversation_id: str) -> dict | None:
    object_id = _safe_object_id(conversation_id)
    if object_id is None:
        return None
    return get_collection(CONVERSATIONS_COLLECTION).find_one({"_id": object_id})


def get_conversation_active_file_state(conversation_id: str) -> dict:
    conversation = get_conversation_by_id(conversation_id) or {}
    return {
        "active_file_id": conversation.get("active_file_id") or "",
        "active_file_name": conversation.get("active_file_name") or "",
        "active_file_mode": conversation.get("active_file_mode") or "",
        "last_file_effective_question": conversation.get("last_file_effective_question") or "",
        "last_file_anchor_text": conversation.get("last_file_anchor_text") or "",
        "last_file_chunk_ids": list(conversation.get("last_file_chunk_ids") or []),
        "active_file_updated_at": conversation.get("active_file_updated_at"),
    }


def get_conversation_topic_state(conversation_id: str) -> dict:
    conversation = get_conversation_by_id(conversation_id) or {}
    return {
        "active_topic_id": conversation.get("active_topic_id") or "",
        "last_topic_anchor": conversation.get("last_topic_anchor") or "",
        "last_topic_focus": conversation.get("last_topic_focus") or "",
        "last_topic_effective_question": conversation.get("last_topic_effective_question") or "",
        "topic_history_buffer": list(conversation.get("topic_history_buffer") or []),
    }


def update_conversation_active_file_state(
    conversation_id: str,
    *,
    active_file_id: str,
    active_file_name: str = "",
    active_file_mode: str = "",
    last_file_effective_question: str = "",
    last_file_anchor_text: str = "",
    last_file_chunk_ids: list[str] | None = None,
) -> None:
    object_id = _safe_object_id(conversation_id)
    if object_id is None:
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    get_collection(CONVERSATIONS_COLLECTION).update_one(
        {"_id": object_id},
        {
            "$set": {
                "active_file_id": active_file_id or None,
                "active_file_name": active_file_name or "",
                "active_file_mode": active_file_mode or "",
                "last_file_effective_question": last_file_effective_question or "",
                "last_file_anchor_text": last_file_anchor_text or "",
                "last_file_chunk_ids": list(last_file_chunk_ids or []),
                "active_file_updated_at": timestamp if active_file_id else None,
                "updated_at": timestamp,
            }
        },
    )


def update_conversation_topic_state(
    conversation_id: str,
    *,
    active_topic_id: str = "",
    last_topic_anchor: str = "",
    last_topic_focus: str = "",
    last_topic_effective_question: str = "",
    topic_history_buffer: list[dict] | None = None,
) -> None:
    object_id = _safe_object_id(conversation_id)
    if object_id is None:
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    get_collection(CONVERSATIONS_COLLECTION).update_one(
        {"_id": object_id},
        {
            "$set": {
                "active_topic_id": active_topic_id or "",
                "last_topic_anchor": last_topic_anchor or "",
                "last_topic_focus": last_topic_focus or "",
                "last_topic_effective_question": last_topic_effective_question or "",
                "topic_history_buffer": list(topic_history_buffer or []),
                "updated_at": timestamp,
            }
        },
    )


def clear_conversation_active_file_state(conversation_id: str) -> None:
    object_id = _safe_object_id(conversation_id)
    if object_id is None:
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    get_collection(CONVERSATIONS_COLLECTION).update_one(
        {"_id": object_id},
        {
            "$set": {
                "active_file_id": None,
                "active_file_name": "",
                "active_file_mode": "",
                "last_file_effective_question": "",
                "last_file_anchor_text": "",
                "last_file_chunk_ids": [],
                "active_file_updated_at": None,
                "updated_at": timestamp,
            }
        },
    )


def _build_cache_key(normalized_question: str) -> str:
    compact_question = " ".join(str(normalized_question).split()).strip()
    compact_question = compact_question.strip("?.! ")
    compact_question = re.sub(r"\s+", " ", compact_question)
    return compact_question.lower()


def _find_legacy_message_cache(normalized_question: str) -> dict | None:
    base_q = normalized_question.strip("?.! ")
    if not base_q:
        return None

    escaped_q = re.escape(base_q)
    pattern = f"^{escaped_q}[?.! ]*$"

    pipeline = [
        {"$match": {
            "role": "user",
            "normalized_question": {"$regex": pattern, "$options": "i"},
            "input_type": "text_only"
        }},
        {"$sort": {"created_at": -1}},
        {"$limit": 1},
    ]

    user_msgs = list(get_collection(MESSAGES_COLLECTION).aggregate(pipeline))
    if not user_msgs:
        return None

    user_msg = user_msgs[0]
    conversation_id = user_msg["conversation_id"]
    user_created_at = user_msg["created_at"]
    assistant_msg = get_collection(MESSAGES_COLLECTION).find_one({
        "conversation_id": conversation_id,
        "role": "assistant",
        "created_at": {"$gt": user_created_at},
    }, sort=[("created_at", 1)])
    if not assistant_msg or not assistant_msg.get("answer"):
        return None

    return {
        "question": user_msg.get("question", normalized_question),
        "normalized_question": user_msg.get("normalized_question", normalized_question),
        "answer": assistant_msg["answer"],
        "router_label": assistant_msg.get("router_label", ""),
    }


def find_cached_answer(normalized_question: str, *, kb_version: str = "") -> dict | None:
    """Find an exact cached answer for text_only requests."""
    cache_key = _build_cache_key(normalized_question)
    if not cache_key:
        return None

    cache_query = {"cache_key": cache_key}
    if kb_version:
        cache_query["kb_version"] = kb_version

    cache_record = get_collection(QA_CACHE_COLLECTION).find_one(cache_query)
    if cache_record:
        if "_id" in cache_record:
            get_collection(QA_CACHE_COLLECTION).update_one(
                {"_id": cache_record["_id"]},
                {
                    "$inc": {"hit_count": 1},
                    "$set": {"updated_at": utc_now_iso()},
                },
            )

        return {
            "answer": cache_record["answer"],
            "router_label": cache_record.get("router_label", ""),
            "cache_key": cache_key,
        }

    if kb_version:
        return None

    legacy_cache = _find_legacy_message_cache(normalized_question)
    if legacy_cache is None:
        return None

    store_cached_answer(
        question=legacy_cache["question"],
        normalized_question=legacy_cache["normalized_question"],
        answer=legacy_cache["answer"],
        router_label=legacy_cache["router_label"],
        source_type="legacy_message_cache",
    )
    return {
        "answer": legacy_cache["answer"],
        "router_label": legacy_cache["router_label"],
        "cache_key": cache_key,
    }


def find_cached_answer_by_cache_key(cache_key: str, *, kb_version: str = "") -> dict | None:
    """Find a cached answer by an already-built cache key."""
    compact_key = _build_cache_key(cache_key)
    if not compact_key:
        return None

    cache_query = {"cache_key": compact_key}
    if kb_version:
        cache_query["kb_version"] = kb_version

    cache_record = get_collection(QA_CACHE_COLLECTION).find_one(cache_query)
    if not cache_record:
        return None

    if "_id" in cache_record:
        get_collection(QA_CACHE_COLLECTION).update_one(
            {"_id": cache_record["_id"]},
            {
                "$inc": {"hit_count": 1},
                "$set": {"updated_at": utc_now_iso()},
            },
        )

    return {
        "answer": cache_record["answer"],
        "router_label": cache_record.get("router_label", ""),
        "cache_key": compact_key,
        "question": cache_record.get("question", ""),
        "normalized_question": cache_record.get("normalized_question", ""),
    }


def store_cached_answer(
    *,
    question: str,
    normalized_question: str,
    answer: str,
    router_label: str = "",
    kb_version: str = "v1",
    source_type: str = "text_only",
) -> str | None:
    """Upsert an exact cache record for future text_only requests."""
    cache_key = _build_cache_key(normalized_question)
    if not cache_key or not str(answer).strip():
        return None

    cache_record = build_exact_cache_record(
        question=question,
        normalized_question=normalized_question,
        cache_key=cache_key,
        answer=answer,
        router_label=router_label,
        kb_version=kb_version,
        source_type=source_type,
    )
    get_collection(QA_CACHE_COLLECTION).update_one(
        {"cache_key": cache_key, "kb_version": cache_record["kb_version"]},
        {
            "$set": {
                "question": cache_record["question"],
                "normalized_question": cache_record["normalized_question"],
                "answer": cache_record["answer"],
                "router_label": cache_record["router_label"],
                "kb_version": cache_record["kb_version"],
                "source_type": cache_record["source_type"],
                "updated_at": cache_record["updated_at"],
            },
            "$setOnInsert": {
                "cache_key": cache_record["cache_key"],
                "created_at": cache_record["created_at"],
                "hit_count": cache_record["hit_count"],
            },
        },
        upsert=True,
    )
    return cache_key


def create_conversation(
    session_id: str,
    user_id: str = "",
    title: str = "",
) -> str:
    record = build_conversation_record(
        session_id=session_id,
        user_id=user_id,
        title=title,
    )
    result = get_collection(CONVERSATIONS_COLLECTION).insert_one(record)

    return str(result.inserted_id)


def add_user_message(
    conversation_id: str,
    question: str,
    normalized_question: str,
    input_type: str,
    effective_question: str = "",
    file_id: str | None = None,
    workflow_context: str = "",
    rewrite_applied: bool = False,
    rewrite_reason: str = "",
) -> str:
    record = build_message_record(
        conversation_id=conversation_id,
        role="user",
        question=question,
        normalized_question=normalized_question,
        effective_question=effective_question,
        input_type=input_type,
        file_id=file_id,
        workflow_context=workflow_context,
        rewrite_applied=rewrite_applied,
        rewrite_reason=rewrite_reason,
    )
    result = get_collection(MESSAGES_COLLECTION).insert_one(record)
    touch_conversation(conversation_id)

    return str(result.inserted_id)


def add_assistant_message(
    conversation_id: str,
    answer: str,
    workflow_context: str = "",
    retrieved_chunk_ids: list[str] | None = None,
    router_label: str = "",
) -> str:
    record = build_message_record(
        conversation_id=conversation_id,
        role="assistant",
        answer=answer,
        workflow_context=workflow_context,
        retrieved_chunk_ids=retrieved_chunk_ids,
        router_label=router_label,
    )
    result = get_collection(MESSAGES_COLLECTION).insert_one(record)
    touch_conversation(conversation_id)

    return str(result.inserted_id)


def list_messages(conversation_id: str) -> list[dict]:
    cursor = get_collection(MESSAGES_COLLECTION).find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1)

    return list(cursor)


def list_file_messages(conversation_id: str, limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []

    cursor = (
        get_collection(MESSAGES_COLLECTION)
        .find(
            {
                "conversation_id": conversation_id,
                "role": "user",
                "file_id": {"$nin": [None, ""]},
            }
        )
        .sort("created_at", -1)
        .limit(limit)
    )

    return list(cursor)


def list_recent_messages(conversation_id: str, limit: int = 6) -> list[dict]:
    if limit <= 0:
        return []

    cursor = get_collection(MESSAGES_COLLECTION).find(
        {"conversation_id": conversation_id}
    ).sort("created_at", -1).limit(limit)

    return list(reversed(list(cursor)))


def get_or_create_conversation(
    session_id: str,
    user_id: str = "",
    title: str = "",
) -> str:
    existing_conversation = get_conversation_by_session(session_id)
    if existing_conversation is not None:
        return str(existing_conversation["_id"])

    return create_conversation(session_id=session_id, user_id=user_id, title=title)


def touch_conversation(conversation_id: str) -> None:
    object_id = _safe_object_id(conversation_id)
    if object_id is None:
        return
    get_collection(CONVERSATIONS_COLLECTION).update_one(
        {"_id": object_id},
        {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
