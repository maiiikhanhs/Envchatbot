from __future__ import annotations

from chromadb import HttpClient
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.config import CHROMA_COLLECTION, CHROMA_HOST, CHROMA_PORT

_chroma_client: ClientAPI | None = None


def get_chroma_client() -> ClientAPI:
    global _chroma_client

    if _chroma_client is None:
        _chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

    return _chroma_client


def get_or_create_collection(
    collection_name: str | None = None,
    metadata: dict | None = None,
) -> Collection:
    target_name = collection_name or CHROMA_COLLECTION

    return get_chroma_client().get_or_create_collection(
        name=target_name,
        metadata=metadata or {"domain": "environment_monitoring"},
    )


def ping_chroma() -> dict:
    heartbeat = get_chroma_client().heartbeat()

    return {
        "status": "success",
        "collection": CHROMA_COLLECTION,
        "heartbeat": heartbeat,
    }
