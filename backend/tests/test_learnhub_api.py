"""/api/learn/* — the contract the web client is coded against, and the auth split.

The frontend (components/learn/LearnSearchBox.tsx, hooks/learn/use-learn-search.ts)
was written against these exact field names in parallel with this router, so the
shape assertions here are the integration test between the two.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import learn
from app.config import settings
from app.middleware.auth import _is_public_path, _is_user_path


def _client() -> TestClient:
    app = FastAPI()
    app.state.limiter = learn.limiter
    app.include_router(learn.router, prefix="/api")
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Auth classification — the split that keeps LLM endpoints from being free     #
# --------------------------------------------------------------------------- #
def test_learn_content_endpoints_are_public():
    for path in (
        "/api/learn/status",
        "/api/learn/search",
        "/api/learn/glossary/search",
        "/api/learn/related",
    ):
        assert _is_public_path(path) is True, f"{path} should be public"


@pytest.mark.parametrize(
    "path", ["/api/learn/ai/quiz-explanation", "/api/learn/ai/summary"]
)
def test_learn_ai_endpoints_are_user_authenticated(path):
    """These spend LLM tokens, so they must require a user JWT.

    auth.py's dispatch checks user paths BEFORE public prefixes, so the
    /api/learn/ai prefix wins over the broader /api/learn — this asserts the
    ordering dependency that makes the split work.
    """
    assert _is_user_path(path) is True, f"{path} must be user-authenticated"


def test_ai_prefix_precedes_the_public_prefix_in_dispatch():
    """Regression guard for the ordering itself: if someone moves the public
    check above the user check in auth.py, LLM endpoints silently go free."""
    import inspect

    from app.middleware import auth

    src = inspect.getsource(auth.BearerTokenMiddleware.dispatch)
    assert src.index("_is_user_path") < src.index("_is_public_path"), (
        "user-path check must run before the public-prefix check, or "
        "/api/learn/ai falls through to the public /api/learn prefix"
    )


# --------------------------------------------------------------------------- #
# Kill switch                                                                  #
# --------------------------------------------------------------------------- #
def test_status_reports_the_flag(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", False)
    assert _client().get("/api/learn/status").json() == {"enabled": False}

    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    assert _client().get("/api/learn/status").json() == {"enabled": True}


def test_flag_off_returns_empty_results_without_touching_retrieval(monkeypatch):
    """Flag off must not reach the DB/embedder at all — and must not error,
    so a direct call degrades to an honest empty rather than a 5xx."""
    monkeypatch.setattr(settings, "learnhub_rag_enabled", False)

    async def _never(*a, **k):  # pragma: no cover
        raise AssertionError("retrieval ran while the flag was off")

    monkeypatch.setattr(learn.retrieval, "search", _never)
    monkeypatch.setattr(learn.retrieval, "related_lessons", _never)

    c = _client()
    assert c.get("/api/learn/search?q=dividend").json() == {"results": []}
    assert c.get("/api/learn/glossary/search?q=dividend").json() == {"results": []}
    assert c.get("/api/learn/related?lesson_id=dividends").json() == {"results": []}


# --------------------------------------------------------------------------- #
# Contract + param validation                                                  #
# --------------------------------------------------------------------------- #
def test_search_response_matches_the_frozen_client_contract(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    row = {
        "lesson_id": "dividends",
        "section_id": "what-is",
        "source_type": "lesson_section",
        "title": "Understanding Dividends",
        "heading": "What is a dividend?",
        "snippet_en": "A dividend is a share of profit…",
        "snippet_ur": "منافع منقسم…",
        "score": 0.0161,
    }

    async def _search(q, *, mode, lesson_id=None, limit=8):
        return [row]

    monkeypatch.setattr(learn.retrieval, "search", _search)

    body = _client().get("/api/learn/search?q=dividend").json()
    assert set(body) == {"results"}
    assert set(body["results"][0]) == set(row)


def test_public_search_never_leaks_full_chunk_text(monkeypatch):
    """retrieval.search() carries text_en/text_ur for the grounding path.
    /api/learn/search is UNAUTHENTICATED — full chunk bodies must not ride it:
    it would bloat every payload and hand the corpus to any caller."""
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)

    async def _search(q, *, mode, lesson_id=None, limit=8):
        return [{
            "lesson_id": "dividend", "section_id": "what-is",
            "source_type": "lesson_section", "title": "T", "heading": "H",
            "snippet_en": "short display cut", "snippet_ur": None, "score": 0.1,
            "text_en": "THE ENTIRE CHUNK BODY " * 50,
            "text_ur": "FULL URDU BODY",
        }]

    monkeypatch.setattr(learn.retrieval, "search", _search)

    for url in ("/api/learn/search?q=dividend", "/api/learn/glossary/search?q=dividend"):
        row = _client().get(url).json()["results"][0]
        assert "text_en" not in row, f"{url} leaked full chunk text"
        assert "text_ur" not in row, f"{url} leaked full Urdu text"
        assert row["snippet_en"] == "short display cut"


def test_search_with_lesson_id_scopes_to_that_lesson(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    seen = {}

    async def _search(q, *, mode, lesson_id=None, limit=8):
        seen.update(mode=mode, lesson_id=lesson_id)
        return []

    monkeypatch.setattr(learn.retrieval, "search", _search)
    _client().get("/api/learn/search?q=dividend&lesson_id=budget")
    assert seen == {"mode": learn.retrieval.MODE_LESSON, "lesson_id": "budget"}


def test_search_without_lesson_id_searches_everything(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    seen = {}

    async def _search(q, *, mode, lesson_id=None, limit=8):
        seen.update(mode=mode)
        return []

    monkeypatch.setattr(learn.retrieval, "search", _search)
    _client().get("/api/learn/search?q=dividend")
    assert seen == {"mode": learn.retrieval.MODE_ALL}


def test_glossary_search_uses_glossary_mode(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    seen = {}

    async def _search(q, *, mode, lesson_id=None, limit=8):
        seen.update(mode=mode)
        return []

    monkeypatch.setattr(learn.retrieval, "search", _search)
    _client().get("/api/learn/glossary/search?q=capital gain")
    assert seen == {"mode": learn.retrieval.MODE_GLOSSARY}


@pytest.mark.parametrize(
    "url",
    [
        "/api/learn/search",  # q is required
        "/api/learn/search?q=a",  # min_length 2
        "/api/learn/search?q=dividend&limit=0",  # ge=1
        "/api/learn/search?q=dividend&limit=99",  # le=20
        "/api/learn/search?q=dividend&lang=fr",  # only en|ur
        "/api/learn/related",  # lesson_id required
    ],
)
def test_invalid_params_are_rejected(url, monkeypatch):
    """Bounded params: an unbounded limit is a free amplification vector on a
    public endpoint."""
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    assert _client().get(url).status_code == 422
