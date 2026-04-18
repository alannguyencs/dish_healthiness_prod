"""
Tests for src/service/personalized_food_index.py.

The service's only DB dependency is
`crud_personalized_food.get_all_rows_for_user`, which is patched to
return a hand-crafted row list per test. This keeps the tests pure
in-process and exercises the tokenizer + BM25 scoring logic directly.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from types import SimpleNamespace
from typing import List, Optional

import pytest

from src.service import personalized_food_index as pfi


def _row(query_id: int, tokens: List[str], *, image_url: str = "", description: str = ""):
    return SimpleNamespace(
        query_id=query_id,
        image_url=image_url or f"/images/{query_id}.jpg",
        description=description or " ".join(tokens),
        tokens=tokens,
    )


@pytest.fixture()
def patch_corpus(monkeypatch):
    """Replace get_all_rows_for_user with a canned-rows factory."""

    def _set(rows):
        def fake(user_id: int, *, exclude_query_id: Optional[int] = None):
            filtered = [
                r for r in rows if exclude_query_id is None or r.query_id != exclude_query_id
            ]
            return filtered

        monkeypatch.setattr(pfi.crud_personalized_food, "get_all_rows_for_user", fake)

    return _set


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Chicken Rice", ["chicken", "rice"]),
        ("  hainanese   style  ", ["hainanese", "style"]),
        ("café — au lait", ["cafe", "au", "lait"]),
        ("ARROZ com FRANGO", ["arroz", "com", "frango"]),
        ("Phở bò", ["pho", "bo"]),
        ("", []),
        ("   ", []),
        ("!!!***", []),
    ],
)
def test_tokenize_normalizes_and_strips(text, expected):
    assert pfi.tokenize(text) == expected


def test_tokenize_is_deterministic():
    text = "Nasi Lemak — ayam rendang"
    assert pfi.tokenize(text) == pfi.tokenize(text)


def test_search_for_user_empty_corpus_returns_empty_list(patch_corpus):
    patch_corpus([])
    assert not pfi.search_for_user(1, ["chicken"], top_k=1)


def test_search_for_user_empty_query_tokens_returns_empty_list(patch_corpus):
    patch_corpus([_row(1, ["chicken", "rice"])])
    assert not pfi.search_for_user(1, [], top_k=1)


def test_search_for_user_returns_top_1_above_threshold(patch_corpus):
    """The 'done when' fixture: 3 rows, top-1 for a real query beats threshold."""
    patch_corpus(
        [
            _row(10, ["chicken", "rice", "hainanese"]),
            _row(11, ["beef", "noodle", "soup"]),
            _row(12, ["chocolate", "chip", "cookie"]),
        ]
    )
    hits = pfi.search_for_user(1, ["chicken", "rice"], top_k=1, min_similarity=0.1)
    assert len(hits) == 1
    assert hits[0]["query_id"] == 10
    assert hits[0]["similarity_score"] > 0.1
    assert hits[0]["similarity_score"] <= 1.0


def test_search_for_user_filters_below_threshold(patch_corpus):
    """Rows with some BM25 score but far below the top still pass above 0.5."""
    patch_corpus(
        [
            _row(10, ["chicken", "rice"]),
            _row(11, ["beef", "noodle"]),
        ]
    )
    all_hits = pfi.search_for_user(1, ["chicken"], top_k=5, min_similarity=0.5)
    assert [h["query_id"] for h in all_hits] == [10]


def test_search_for_user_returns_empty_when_no_token_matches(patch_corpus):
    patch_corpus([_row(10, ["chicken", "rice"])])
    assert not pfi.search_for_user(1, ["sushi", "roll"], top_k=5, min_similarity=0.0)


def test_search_for_user_respects_exclude_query_id(patch_corpus):
    patch_corpus(
        [
            _row(10, ["chicken", "rice"]),
            _row(11, ["chicken", "rice"]),
        ]
    )
    hits = pfi.search_for_user(
        1, ["chicken", "rice"], top_k=5, min_similarity=0.0, exclude_query_id=11
    )
    assert [h["query_id"] for h in hits] == [10]


def test_search_for_user_scopes_to_user_id(monkeypatch):
    rows_by_user = {
        1: [_row(10, ["chicken", "rice"])],
        2: [_row(20, ["sushi", "roll"])],
    }

    def fake(user_id, *, exclude_query_id=None):
        rows = rows_by_user.get(user_id, [])
        return [r for r in rows if exclude_query_id is None or r.query_id != exclude_query_id]

    monkeypatch.setattr(pfi.crud_personalized_food, "get_all_rows_for_user", fake)

    hits_a = pfi.search_for_user(1, ["chicken"], top_k=5, min_similarity=0.0)
    assert [h["query_id"] for h in hits_a] == [10]
    hits_b = pfi.search_for_user(2, ["sushi"], top_k=5, min_similarity=0.0)
    assert [h["query_id"] for h in hits_b] == [20]


def test_search_for_user_return_shape_is_stable(patch_corpus):
    row = _row(10, ["chicken", "rice"], image_url="/images/10.jpg", description="chicken rice")
    patch_corpus([row])
    hits = pfi.search_for_user(1, ["chicken"], top_k=1, min_similarity=0.0)
    assert len(hits) == 1
    hit = hits[0]
    assert set(hit.keys()) == {"query_id", "image_url", "description", "similarity_score", "row"}
    assert hit["query_id"] == 10
    assert hit["image_url"] == "/images/10.jpg"
    assert hit["description"] == "chicken rice"
    assert 0.0 <= hit["similarity_score"] <= 1.0
    assert hit["row"] is row


def test_search_for_user_skips_rows_with_empty_tokens(patch_corpus):
    patch_corpus(
        [
            _row(10, []),
            _row(11, ["chicken", "rice"]),
        ]
    )
    hits = pfi.search_for_user(1, ["chicken"], top_k=5, min_similarity=0.0)
    assert [h["query_id"] for h in hits] == [11]
