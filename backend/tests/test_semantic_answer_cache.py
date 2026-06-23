from __future__ import annotations

import json

import app.services.semantic_answer_cache as semantic_cache


class FakeCollection:
    def __init__(self, query_result=None):
        self.query_result = query_result or {}
        self.upserts = []

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return self.query_result

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def _enable_semantic_cache(monkeypatch):
    monkeypatch.setattr(semantic_cache, "SEMANTIC_ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(semantic_cache, "SEMANTIC_ANSWER_CACHE_VERIFIER_URL", "https://verifier.test/chat")
    monkeypatch.setattr(semantic_cache, "SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL", "small-verifier")
    monkeypatch.setattr(semantic_cache, "SEMANTIC_ANSWER_CACHE_MIN_SIMILARITY", 0.88)
    monkeypatch.setattr(semantic_cache, "SEMANTIC_ANSWER_CACHE_VERIFIER_MIN_CONFIDENCE", 0.90)
    monkeypatch.setattr(semantic_cache, "generate_real_embedding", lambda text: [0.1, 0.2, 0.3])


def test_semantic_lookup_returns_cache_when_verifier_allows(monkeypatch):
    _enable_semantic_cache(monkeypatch)
    collection = FakeCollection(
        {
            "metadatas": [[{"cache_key": "cached question"}]],
            "distances": [[0.05]],
        }
    )
    monkeypatch.setattr(semantic_cache, "_semantic_collection", lambda: collection)
    monkeypatch.setattr(
        semantic_cache.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json.dumps({"safe_to_reuse": True, "confidence": 0.96, "reason": "same"})
        ),
    )

    result = semantic_cache.lookup_semantic_cached_answer(
        question="current question",
        conversation_context="",
        kb_version="kb-v1",
        find_cached_answer_by_cache_key_fn=lambda *args, **kwargs: {
            "answer": "cached answer",
            "router_label": "PHAP_LY",
            "cache_key": "cached question",
            "normalized_question": "cached question",
        },
    )

    assert result["answer"] == "cached answer"
    assert result["cache_type"] == "semantic"
    assert result["semantic_similarity"] == 0.95
    assert collection.query_kwargs["where"] == {"kb_version": "kb-v1"}


def test_semantic_lookup_fails_safe_when_verifier_rejects(monkeypatch):
    _enable_semantic_cache(monkeypatch)
    collection = FakeCollection(
        {
            "metadatas": [[{"cache_key": "cached question"}]],
            "distances": [[0.05]],
        }
    )
    monkeypatch.setattr(semantic_cache, "_semantic_collection", lambda: collection)
    monkeypatch.setattr(
        semantic_cache.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            json.dumps({"safe_to_reuse": False, "confidence": 0.99, "reason": "different"})
        ),
    )

    result = semantic_cache.lookup_semantic_cached_answer(
        question="current question",
        conversation_context="",
        kb_version="kb-v1",
        find_cached_answer_by_cache_key_fn=lambda *args, **kwargs: {
            "answer": "cached answer",
            "router_label": "PHAP_LY",
            "cache_key": "cached question",
            "normalized_question": "cached question",
        },
    )

    assert result is None


def test_semantic_upsert_stores_metadata_without_answer(monkeypatch):
    _enable_semantic_cache(monkeypatch)
    collection = FakeCollection()
    monkeypatch.setattr(semantic_cache, "_semantic_collection", lambda: collection)

    semantic_cache.upsert_semantic_answer_cache(
        cache_key="cached question",
        question="cached question",
        router_label="PHAP_LY",
        kb_version="kb-v1",
    )

    metadata = collection.upserts[0]["metadatas"][0]
    assert metadata == {
        "cache_key": "cached question",
        "question": "cached question",
        "router_label": "PHAP_LY",
        "kb_version": "kb-v1",
        "source_type": "text_only",
    }
    assert "answer" not in metadata
