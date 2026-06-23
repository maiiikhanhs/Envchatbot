from __future__ import annotations

from typing import Iterable

from app.config import CHROMA_COLLECTION
from app.database.chroma import get_or_create_collection


def upsert_chunk_embeddings(
    chunks: Iterable[dict],
    collection_name: str = CHROMA_COLLECTION,
) -> int:
    chunk_list = list(chunks)

    if not chunk_list:
        return 0

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for chunk in chunk_list:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["content"])
        embeddings.append(chunk["embedding"])
        metadatas.append(_build_chroma_metadata(chunk))

    get_or_create_collection(collection_name).upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(chunk_list)


def query_similar_chunks(
    question_embedding: list[float],
    top_k: int = 5,
    collection_name: str = CHROMA_COLLECTION,
    where: dict | None = None,
) -> dict:
    return get_or_create_collection(collection_name).query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        where=where,
    )


from app.retrieval.embedding import generate_real_embedding


def query_similar_chunks_by_question(
    question: str,
    top_k: int = 5,
    collection_name: str = CHROMA_COLLECTION,
    where: dict | None = None,
) -> list[dict]:
    question_embedding = generate_real_embedding(question)
    query_result = query_similar_chunks(
        question_embedding=question_embedding,
        top_k=top_k,
        collection_name=collection_name,
        where=where,
    )

    ids = query_result.get("ids", [[]])
    documents = query_result.get("documents", [[]])
    metadatas = query_result.get("metadatas", [[]])
    distances = query_result.get("distances", [[]])

    first_ids = ids[0] if ids else []
    first_documents = documents[0] if documents else []
    first_metadatas = metadatas[0] if metadatas else []
    first_distances = distances[0] if distances else []

    retrieved_chunks = []
    for index, chunk_id in enumerate(first_ids):
        metadata = first_metadatas[index] if index < len(first_metadatas) else {}
        content = first_documents[index] if index < len(first_documents) else ""
        distance = first_distances[index] if index < len(first_distances) else 0.0

        retrieved_chunks.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "chunk_index": int(metadata.get("chunk_index", index + 1)),
                "char_count": len(content),
                "word_count": len(content.split()),
                "source_file_name": metadata.get("source_file_name"),
                "source_file_extension": metadata.get("source_file_extension"),
                "document_id": metadata.get("document_id"),
                "category": metadata.get("category", ""),
                "source_group": metadata.get("source_group", ""),
                "kb_version": metadata.get("kb_version", "v1"),
                "similarity_score": max(0.0, round(1 - float(distance), 6)),
            }
        )

    return retrieved_chunks


def _build_chroma_metadata(chunk: dict) -> dict:
    return {
        "document_id": str(chunk.get("document_id", "")),
        "chunk_index": int(chunk.get("chunk_index", 0)),
        "source_file_name": str(chunk.get("source_file_name", "")),
        "source_file_extension": str(chunk.get("source_file_extension", "")),
        "category": str(chunk.get("category", "")),
        "source_group": str(chunk.get("source_group", "user_upload")),
        "kb_version": str(chunk.get("kb_version", "v1")),
    }
