from __future__ import annotations

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import MONGODB_DB_NAME, MONGODB_FALLBACK_URI, MONGODB_URI

DOCUMENTS_COLLECTION = "documents"
DOCUMENT_CHUNKS_COLLECTION = "document_chunks"
CONVERSATIONS_COLLECTION = "conversations"
MESSAGES_COLLECTION = "messages"
QA_CACHE_COLLECTION = "qa_cache"
REPORTS_COLLECTION = "reports"

_mongo_client: MongoClient | None = None
_mongo_uri_in_use: str | None = None


def _create_client(uri: str) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    return client


def get_mongo_client() -> MongoClient:
    global _mongo_client, _mongo_uri_in_use

    if _mongo_client is None:
        primary_error: Exception | None = None

        try:
            _mongo_client = _create_client(MONGODB_URI)
            _mongo_uri_in_use = MONGODB_URI
        except PyMongoError as exc:
            primary_error = exc
            if MONGODB_FALLBACK_URI and MONGODB_FALLBACK_URI != MONGODB_URI:
                _mongo_client = _create_client(MONGODB_FALLBACK_URI)
                _mongo_uri_in_use = MONGODB_FALLBACK_URI
            else:
                raise primary_error

    return _mongo_client


def get_mongo_database() -> Database:
    return get_mongo_client()[MONGODB_DB_NAME]


def get_collection(collection_name: str) -> Collection:
    return get_mongo_database()[collection_name]


def ensure_mongo_indexes() -> None:
    database = get_mongo_database()

    database[DOCUMENTS_COLLECTION].create_index(
        [("document_code", ASCENDING)], unique=False
    )
    database[DOCUMENTS_COLLECTION].create_index([("category", ASCENDING)])
    database[DOCUMENTS_COLLECTION].create_index([("source_group", ASCENDING)])
    database[DOCUMENTS_COLLECTION].create_index([("kb_version", ASCENDING)])
    database[DOCUMENTS_COLLECTION].create_index([("vector_backend", ASCENDING)])
    database[DOCUMENTS_COLLECTION].create_index([("vector_status", ASCENDING)])

    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("document_id", ASCENDING)])
    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("chunk_id", ASCENDING)], unique=True)
    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("kb_version", ASCENDING)])
    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("source_group", ASCENDING)])
    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("vector_backend", ASCENDING)])
    database[DOCUMENT_CHUNKS_COLLECTION].create_index([("vector_status", ASCENDING)])

    database[CONVERSATIONS_COLLECTION].create_index([("session_id", ASCENDING)])
    database[CONVERSATIONS_COLLECTION].create_index([("updated_at", DESCENDING)])

    database[MESSAGES_COLLECTION].create_index([("conversation_id", ASCENDING)])
    database[MESSAGES_COLLECTION].create_index([("created_at", DESCENDING)])
    database[MESSAGES_COLLECTION].create_index([("router_label", ASCENDING)])

    database[QA_CACHE_COLLECTION].create_index(
        [("cache_key", ASCENDING), ("kb_version", ASCENDING)], unique=True
    )
    database[QA_CACHE_COLLECTION].create_index([("updated_at", DESCENDING)])

    database[REPORTS_COLLECTION].create_index([("created_at", DESCENDING)])
    database[REPORTS_COLLECTION].create_index([("status", ASCENDING)])
    database[REPORTS_COLLECTION].create_index([("report_type", ASCENDING)])
    database[REPORTS_COLLECTION].create_index([("user_id", ASCENDING)])
    database[REPORTS_COLLECTION].create_index([("conversation_id", ASCENDING)])
    database[REPORTS_COLLECTION].create_index([("message_id", ASCENDING)])


def ping_mongo() -> dict:
    get_mongo_client().admin.command("ping")

    return {
        "status": "success",
        "database": MONGODB_DB_NAME,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
