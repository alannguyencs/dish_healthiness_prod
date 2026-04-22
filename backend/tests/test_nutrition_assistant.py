"""
Unit tests for `backend/src/service/llm/nutrition_assistant.py` (Stage 10).

Covers:
  - Prompt rendering substitutes `{{BASELINE_JSON}}` + `{{USER_HINT}}`.
  - Baseline selection prefers `step2_corrected` over `step2_data`
    (current-effective-payload semantics).
  - The trim helper drops engineering metadata + ai_assistant_prompt.
  - Missing image on disk raises `FileNotFoundError`.
  - Missing baseline raises `ValueError`.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name
# pylint: disable=protected-access,unused-argument

from types import SimpleNamespace

import pytest

from src.service.llm import nutrition_assistant


@pytest.fixture()
def tmp_image(tmp_path):
    p = tmp_path / "img.jpg"
    p.write_bytes(b"fake-jpeg-bytes")
    return p


def _record_with(result_gemini, image_url):
    return SimpleNamespace(
        id=1,
        user_id=42,
        image_url=image_url,
        result_gemini=result_gemini,
    )


def test_trim_drops_metadata_and_audit_fields():
    baseline = {
        "dish_name": "X",
        "healthiness_score": 70,
        "healthiness_score_rationale": "r",
        "calories_kcal": 500,
        "fiber_g": 5,
        "carbs_g": 50,
        "protein_g": 30,
        "fat_g": 15,
        "micronutrients": ["Iron"],
        "model": "gemini-2.5-pro",
        "price_usd": 0.01,
        "analysis_time": 8.3,
        "input_token": 1200,
        "output_token": 300,
        "ai_assistant_prompt": "earlier hint",
    }
    trimmed = nutrition_assistant._trim_baseline_for_prompt(baseline)
    # Kept
    assert trimmed["calories_kcal"] == 500
    assert trimmed["micronutrients"] == ["Iron"]
    # Dropped
    assert "model" not in trimmed
    assert "price_usd" not in trimmed
    assert "analysis_time" not in trimmed
    assert "input_token" not in trimmed
    assert "output_token" not in trimmed
    assert "ai_assistant_prompt" not in trimmed


def test_render_substitutes_baseline_and_hint(tmp_path, monkeypatch):
    baseline = {"dish_name": "Ayam", "calories_kcal": 600}
    rendered = nutrition_assistant._render_assistant_prompt(baseline, "smaller portion")
    assert '"dish_name": "Ayam"' in rendered
    assert "smaller portion" in rendered
    # Placeholders replaced
    assert "{{BASELINE_JSON}}" not in rendered
    assert "{{USER_HINT}}" not in rendered


@pytest.mark.asyncio
async def test_revise_uses_step2_corrected_when_present(monkeypatch, tmp_image):
    captured = {}

    async def fake_analyzer(image_path, analysis_prompt, gemini_model, thinking_budget):
        captured["prompt"] = analysis_prompt
        captured["image_path"] = image_path
        captured["model"] = gemini_model
        return {"calories_kcal": 300, "dish_name": "Ayam"}

    monkeypatch.setattr(nutrition_assistant, "analyze_nutritional_analysis_async", fake_analyzer)
    monkeypatch.setattr(nutrition_assistant, "IMAGE_DIR", tmp_image.parent)
    monkeypatch.setattr(
        nutrition_assistant,
        "get_dish_image_query_by_id",
        lambda _id: _record_with(
            {
                "nutrition_data": {"calories_kcal": 600, "dish_name": "Ayam"},
                "nutrition_corrected": {"calories_kcal": 9999, "dish_name": "Ayam"},
            },
            tmp_image.name,
        ),
    )

    result = await nutrition_assistant.revise_nutrition_with_hint(1, "fix this")

    assert result["calories_kcal"] == 300
    # Prompt contains the corrected baseline (9999), not the raw step2_data (600)
    assert "9999" in captured["prompt"]
    assert "fix this" in captured["prompt"]
    assert captured["model"] == "gemini-2.5-pro"


@pytest.mark.asyncio
async def test_revise_falls_back_to_step2_data_when_no_corrected(monkeypatch, tmp_image):
    captured = {}

    async def fake_analyzer(image_path, analysis_prompt, gemini_model, thinking_budget):
        captured["prompt"] = analysis_prompt
        return {"calories_kcal": 500, "dish_name": "Ayam"}

    monkeypatch.setattr(nutrition_assistant, "analyze_nutritional_analysis_async", fake_analyzer)
    monkeypatch.setattr(nutrition_assistant, "IMAGE_DIR", tmp_image.parent)
    monkeypatch.setattr(
        nutrition_assistant,
        "get_dish_image_query_by_id",
        lambda _id: _record_with(
            {"nutrition_data": {"calories_kcal": 600, "dish_name": "Ayam"}},
            tmp_image.name,
        ),
    )

    result = await nutrition_assistant.revise_nutrition_with_hint(1, "use baseline")

    assert result["calories_kcal"] == 500
    # Prompt uses step2_data baseline (600)
    assert "600" in captured["prompt"]


@pytest.mark.asyncio
async def test_revise_raises_when_image_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(nutrition_assistant, "IMAGE_DIR", tmp_path)
    monkeypatch.setattr(
        nutrition_assistant,
        "get_dish_image_query_by_id",
        lambda _id: _record_with(
            {"nutrition_data": {"calories_kcal": 500}},
            "not_on_disk.jpg",
        ),
    )

    async def fake_analyzer(*args, **kwargs):
        return {"calories_kcal": 1}

    monkeypatch.setattr(nutrition_assistant, "analyze_nutritional_analysis_async", fake_analyzer)

    with pytest.raises(FileNotFoundError):
        await nutrition_assistant.revise_nutrition_with_hint(1, "hint")


@pytest.mark.asyncio
async def test_revise_raises_when_no_baseline(monkeypatch, tmp_image):
    monkeypatch.setattr(nutrition_assistant, "IMAGE_DIR", tmp_image.parent)
    monkeypatch.setattr(
        nutrition_assistant,
        "get_dish_image_query_by_id",
        lambda _id: _record_with({"phase": 1}, tmp_image.name),
    )

    with pytest.raises(ValueError):
        await nutrition_assistant.revise_nutrition_with_hint(1, "hint")


@pytest.mark.asyncio
async def test_revise_raises_when_record_missing(monkeypatch):
    monkeypatch.setattr(nutrition_assistant, "get_dish_image_query_by_id", lambda _id: None)
    with pytest.raises(ValueError):
        await nutrition_assistant.revise_nutrition_with_hint(999, "hint")
