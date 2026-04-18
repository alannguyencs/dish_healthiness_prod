"""
Endpoint tests for POST /api/date/{y}/{m}/{d}/upload (and /upload-url).

Focus: re-uploading the same slot REPLACES the prior row instead of leaving
an orphan. The endpoint delegates the dedupe to `replace_slot_atomic`, so
the contract verified here is:

* the endpoint passes the right slot key into the CRUD,
* it cleans up the old image file(s) on disk for any URLs the CRUD returns,
* it schedules a single Phase-1 background task per upload.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

import io
from types import SimpleNamespace

import pytest
from PIL import Image

from src.api import date as date_api


@pytest.fixture()
def patch_auth(monkeypatch, fake_user):
    monkeypatch.setattr(date_api, "authenticate_user_from_request", lambda _r: fake_user)


@pytest.fixture()
def mock_image_dir(tmp_path, monkeypatch):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    monkeypatch.setattr(date_api, "IMAGE_DIR", image_dir)
    return image_dir


@pytest.fixture()
def captured_tasks(monkeypatch):
    calls = []

    def _capture(self, func, *args, **kwargs):  # pylint: disable=unused-argument
        calls.append({"func": func, "args": args, "kwargs": kwargs})

    from fastapi import BackgroundTasks  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(BackgroundTasks, "add_task", _capture)
    return calls


@pytest.fixture()
def captured_replace(monkeypatch):
    """Spy on replace_slot_atomic; default returns (new_row, []) (no orphan)."""
    calls = []
    next_row_id = {"n": 100}

    def _replace(*, user_id, target_date, dish_position, image_url):
        next_row_id["n"] += 1
        calls.append(
            {
                "user_id": user_id,
                "target_date": target_date,
                "dish_position": dish_position,
                "image_url": image_url,
            }
        )
        new_row = SimpleNamespace(
            id=next_row_id["n"],
            user_id=user_id,
            image_url=image_url,
            dish_position=dish_position,
            created_at=None,
            target_date=target_date,
            result_openai=None,
            result_gemini=None,
        )
        # replace_slot_atomic is patched per-test for replacement scenarios;
        # this default returns no orphans.
        return new_row, calls[-1].get("__orphans__", [])

    monkeypatch.setattr(date_api, "replace_slot_atomic", _replace)
    return calls


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color=(120, 200, 80))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Auth + validation
# ---------------------------------------------------------------------------


def test_upload_returns_401_when_not_authenticated(client, monkeypatch):
    monkeypatch.setattr(date_api, "authenticate_user_from_request", lambda _r: None)
    res = client.post(
        "/api/date/2026/4/18/upload",
        data={"dish_position": "1"},
        files={"file": ("a.jpg", b"x", "image/jpeg")},
    )
    assert res.status_code == 401


def test_upload_rejects_position_above_max(
    client, patch_auth, mock_image_dir, captured_tasks, captured_replace
):
    res = client.post(
        "/api/date/2026/4/18/upload",
        data={"dish_position": "9"},
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 400
    assert captured_replace == []  # no DB write
    assert captured_tasks == []  # no background task


def test_upload_rejects_invalid_date(
    client, patch_auth, mock_image_dir, captured_tasks, captured_replace
):
    res = client.post(
        "/api/date/2026/13/18/upload",
        data={"dish_position": "1"},
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 400
    assert captured_replace == []


# ---------------------------------------------------------------------------
# Slot dedupe (the bug)
# ---------------------------------------------------------------------------


def test_first_upload_passes_slot_key_to_replace_slot(
    client, patch_auth, mock_image_dir, captured_tasks, captured_replace
):
    res = client.post(
        "/api/date/2026/4/18/upload",
        data={"dish_position": "2"},
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 200
    assert len(captured_replace) == 1
    call = captured_replace[0]
    assert call["dish_position"] == 2
    assert call["target_date"].date().isoformat() == "2026-04-18"
    assert call["image_url"].startswith("/images/")
    # Filename now includes user_id to prevent cross-user same-second collisions.
    assert "_u42_" in call["image_url"]
    assert call["image_url"].endswith("_dish2.jpg")
    assert len(captured_tasks) == 1


def test_re_upload_to_same_slot_deletes_prior_image_file(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    """The orphan-row bug: a re-upload must clean up the prior image file."""
    orphan_filename = "240101_120000_dish3.jpg"
    orphan_path = mock_image_dir / orphan_filename
    orphan_path.write_bytes(b"old")
    assert orphan_path.exists()

    def _replace(*, user_id, target_date, dish_position, image_url):
        # Simulate an existing slot row being replaced — return its image_url.
        new_row = SimpleNamespace(
            id=999,
            user_id=user_id,
            image_url=image_url,
            dish_position=dish_position,
            created_at=None,
            target_date=target_date,
            result_openai=None,
            result_gemini=None,
        )
        return new_row, [f"/images/{orphan_filename}"]

    monkeypatch.setattr(date_api, "replace_slot_atomic", _replace)

    res = client.post(
        "/api/date/2026/4/18/upload",
        data={"dish_position": "3"},
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 200
    # Critical: the orphan image file is gone after re-upload.
    assert not orphan_path.exists()
    assert len(captured_tasks) == 1


def test_re_upload_tolerates_already_missing_orphan_image(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks
):
    """If the orphan disk file vanished out-of-band, re-upload still succeeds."""

    def _replace(*, user_id, target_date, dish_position, image_url):
        new_row = SimpleNamespace(
            id=1,
            user_id=user_id,
            image_url=image_url,
            dish_position=dish_position,
            created_at=None,
            target_date=target_date,
            result_openai=None,
            result_gemini=None,
        )
        return new_row, ["/images/this_file_was_already_deleted.jpg"]

    monkeypatch.setattr(date_api, "replace_slot_atomic", _replace)

    res = client.post(
        "/api/date/2026/4/18/upload",
        data={"dish_position": "1"},
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 200
    assert len(captured_tasks) == 1


# ---------------------------------------------------------------------------
# /upload-url path uses the same dedupe
# ---------------------------------------------------------------------------


def test_upload_url_uses_replace_slot_atomic(
    client, monkeypatch, patch_auth, mock_image_dir, captured_tasks, captured_replace
):
    async def _fake_get(self, url, *_, **__):
        return SimpleNamespace(
            content=_jpeg_bytes(),
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)

    res = client.post(
        "/api/date/2026/4/18/upload-url",
        json={"dish_position": 4, "image_url": "https://example.com/x.jpg"},
    )
    assert res.status_code == 200
    assert len(captured_replace) == 1
    assert captured_replace[0]["dish_position"] == 4
    assert len(captured_tasks) == 1
