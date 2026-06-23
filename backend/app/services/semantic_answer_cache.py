from __future__ import annotations

import json
from typing import Callable

import requests

from app.config import (
    SEMANTIC_ANSWER_CACHE_COLLECTION,
    SEMANTIC_ANSWER_CACHE_ENABLED,
    SEMANTIC_ANSWER_CACHE_MIN_SIMILARITY,
    SEMANTIC_ANSWER_CACHE_VERIFIER_API_KEY,
    SEMANTIC_ANSWER_CACHE_VERIFIER_MIN_CONFIDENCE,
    SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL,
    SEMANTIC_ANSWER_CACHE_VERIFIER_TIMEOUT,
    SEMANTIC_ANSWER_CACHE_VERIFIER_URL,
)
from app.database.chroma import get_or_create_collection
from app.retrieval.embedding import generate_real_embedding

SEMANTIC_CACHE_TOP_K = 3
SEMANTIC_CACHE_CONTEXT_LIMIT = 1800
SEMANTIC_CACHE_ANSWER_LIMIT = 2200

VERIFIER_SYSTEM_PROMPT = """You are a strict cache reuse verifier.
Do not answer the user's question.
Decide whether the cached answer can be safely reused for the current question.
Return only compact JSON with keys: safe_to_reuse, confidence, reason.
Use safe_to_reuse=false when intent, subject, scope, context, or answer coverage is uncertain."""


def _enabled() -> bool:
    return bool(
        SEMANTIC_ANSWER_CACHE_ENABLED
        and SEMANTIC_ANSWER_CACHE_VERIFIER_URL
        and SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL
    )


def _clip(text: str, limit: int) -> str:
    compacted = " ".join(str(text or "").split())
    return compacted[:limit]


def _semantic_collection():
    return get_or_create_collection(
        SEMANTIC_ANSWER_CACHE_COLLECTION,
        metadata={"domain": "environment_monitoring", "hnsw:space": "cosine"},
    )


def _similarity_from_distance(distance) -> float:
    try:
        return max(0.0, min(1.0, 1.0 - float(distance)))
    except (TypeError, ValueError):
        return 0.0


def _verify_cache_reuse(
    *,
    current_question: str,
    conversation_context: str,
    cached_question: str,
    cached_answer: str,
) -> dict:
    payload = {
        "current_question": _clip(current_question, 1200),
        "conversation_context": _clip(conversation_context, SEMANTIC_CACHE_CONTEXT_LIMIT),
        "cached_question": _clip(cached_question, 1200),
        "cached_answer": _clip(cached_answer, SEMANTIC_CACHE_ANSWER_LIMIT),
    }
    headers = {"Content-Type": "application/json"}
    if SEMANTIC_ANSWER_CACHE_VERIFIER_API_KEY:
        headers["Authorization"] = f"Bearer {SEMANTIC_ANSWER_CACHE_VERIFIER_API_KEY}"

    response = requests.post(
        SEMANTIC_ANSWER_CACHE_VERIFIER_URL,
        headers=headers,
        json={
            "model": SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL,
            "messages": [
                {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": 128,
        },
        timeout=SEMANTIC_ANSWER_CACHE_VERIFIER_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    verdict = json.loads(content)
    return verdict if isinstance(verdict, dict) else {}


def lookup_semantic_cached_answer(
    *,
    question: str,
    conversation_context: str,
    kb_version: str,
    find_cached_answer_by_cache_key_fn: Callable[..., dict | None],
) -> dict | None:
    if not _enabled() or not str(question or "").strip():
        return None

    try:
        query_result = _semantic_collection().query(
            query_embeddings=[generate_real_embedding(question)],
            n_results=SEMANTIC_CACHE_TOP_K,
            where={"kb_version": kb_version} if kb_version else None,
        )
        metadatas = (query_result.get("metadatas") or [[]])[0]
        distances = (query_result.get("distances") or [[]])[0]
    except Exception:
        return None

    for index, metadata in enumerate(metadatas):
        similarity = _similarity_from_distance(
            distances[index] if index < len(distances) else None
        )
        if similarity < SEMANTIC_ANSWER_CACHE_MIN_SIMILARITY:
            continue

        cached = find_cached_answer_by_cache_key_fn(
            str((metadata or {}).get("cache_key", "")),
            kb_version=kb_version,
        )
        if not cached:
            continue

        try:
            verdict = _verify_cache_reuse(
                current_question=question,
                conversation_context=conversation_context,
                cached_question=cached.get("normalized_question") or cached.get("question", ""),
                cached_answer=cached.get("answer", ""),
            )
        except Exception:
            return None

        if (
            verdict.get("safe_to_reuse") is True
            and float(verdict.get("confidence", 0)) >= SEMANTIC_ANSWER_CACHE_VERIFIER_MIN_CONFIDENCE
        ):
            return {
                **cached,
                "cache_type": "semantic",
                "semantic_similarity": similarity,
                "verifier_confidence": float(verdict.get("confidence", 0)),
                "verifier_reason": str(verdict.get("reason", "")),
            }

    return None


def upsert_semantic_answer_cache(
    *,
    cache_key: str | None,
    question: str,
    router_label: str,
    kb_version: str,
) -> None:
    if not _enabled() or not cache_key or not str(question or "").strip():
        return

    try:
        _semantic_collection().upsert(
            ids=[cache_key],
            documents=[question],
            embeddings=[generate_real_embedding(question)],
            metadatas=[
                {
                    "cache_key": cache_key,
                    "question": question,
                    "router_label": router_label or "",
                    "kb_version": kb_version or "",
                    "source_type": "text_only",
                }
            ],
        )
    except Exception:
        return
