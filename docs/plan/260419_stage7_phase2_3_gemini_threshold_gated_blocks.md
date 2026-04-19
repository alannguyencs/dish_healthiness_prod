# Stage 7 — Phase 2.3: Gemini Analysis with Threshold-Gated Reference Blocks

**Feature**: The Step 2 Gemini 2.5 Pro call becomes the consumer of the evidence Stages 5 and 6 persist. Two new threshold-gated blocks (`__NUTRITION_DB_BLOCK__`, `__PERSONALIZED_BLOCK__`) are substituted into `step2_nutritional_analysis.md` only when their gates pass; the top-1 personalization match's image is optionally attached as a second image part at `similarity_score ≥ 0.35`. The Step 2 output schema gains seven flat `reasoning_*` strings so the model cites which source drove each number. Backend-only — no UI change in this stage; Stage 8 surfaces the reasoning panel.
**Plan Created:** 2026-04-19
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 7](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 5 Phase 2.1](./260419_stage5_phase2_1_nutrition_db_lookup.md) (produces `nutrition_db_matches`)
- [Plan — Stage 6 Phase 2.2](./260419_stage6_phase2_2_personalization_lookup.md) (produces `personalized_matches`)
- [Plan — Stage 3 Phase 1.1.2](./260418_stage3_phase1_1_2_reference_assisted_component_id.md) (placeholder-substitution precedent)
- [Abstract — Nutritional Analysis](../abstract/dish_analysis/nutritional_analysis.md)
- [Technical — Nutritional Analysis](../technical/dish_analysis/nutritional_analysis.md)
- [Technical — Nutrition DB](../technical/dish_analysis/nutrition_db.md)
- [Technical — Personalized Food Index](../technical/dish_analysis/personalized_food_index.md)
- [Chrome Test Spec — 260419_1053](../chrome_test/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks.md)

---

## Problem Statement

1. Stages 5 and 6 persist `result_gemini.nutrition_db_matches` and `result_gemini.personalized_matches` on every Phase 2 run, but nothing in the pipeline reads them. The Step 2 Gemini call ignores the evidence; macro numbers and rationale are LLM-only. Stage 7 is the wiring that makes the prior four stages pay off.
2. The prompt must not pass low-confidence noise to the model. A weak DB match or a dissimilar prior upload would drag estimates toward the wrong reference. The end-to-end discussion pins three thresholds:
   - `THRESHOLD_DB_INCLUDE = 80` (compared against `nutrition_db_matches.nutrition_matches[0].confidence_score`, 0–100 scale).
   - `THRESHOLD_PERSONALIZATION_INCLUDE = 0.30` (against `personalized_matches[0].similarity_score`, 0–1 scale).
   - `THRESHOLD_PHASE_2_2_IMAGE = 0.35` (against the same `similarity_score`, for the image-B attach).
3. The Step 2 output schema today returns numbers without attribution. Stage 8's review UI needs to show the user which source drove each number — otherwise the AI's "reasoning" stays opaque. The schema gains seven flat `reasoning_*` strings (Gemini structured-output cannot handle nested schemas); each defaults to `""` so cold-start / low-confidence paths don't break the analyzer.
4. The prompt needs to be told that omitted blocks are **authoritatively absent**, not to be inferred. Without that instruction, Gemini is prone to "halluci-cite" a DB source that was gated out — Stage 8's UI would then show a citation for a block the user never saw.
5. The failure surface must not grow. Every Stage 7 degradation (threshold fail, missing image file, malformed matches payload) falls back to today's single-image + placeholder-stripped prompt. Step 2 must not start failing on queries that pass today.

---

## Proposed Solution

Six artifacts change, none added:

1. **`backend/resources/step2_nutritional_analysis.md`** — append two placeholder markers and one new instruction line. Placeholders live on their own lines so the strip regex removes the line cleanly (symmetric with Stage 3's `__REFERENCE_BLOCK__`).

2. **`backend/src/service/llm/models.py::Step2NutritionalAnalysis`** — add seven `reasoning_*: str = Field(default="", description=...)` fields at the class level. Flat siblings of the macros. `Field(default="")` so the analyzer's required-field guard is unaffected.

3. **`backend/src/service/llm/prompts.py::get_step2_nutritional_analysis_prompt`** — new signature `(dish_name, components, nutrition_db_matches=None, personalized_matches=None)`. Gate + substitute or strip each placeholder. JSON-dump a trimmed subset of each matches list so the outbound prompt stays human-readable in the backend log.

4. **`backend/src/service/llm/gemini_analyzer.py::analyze_step2_nutritional_analysis_async`** — new `reference_image_bytes=None` parameter. When set, append a second `types.Part.from_bytes` after the query image. Symmetric with Stage 3's Phase 1.1.2 two-image path.

5. **`backend/src/api/item_tasks.py::trigger_step2_analysis_background`** — read `nutrition_db_matches` + `personalized_matches` from the pre-Pro-persisted `result_gemini`, resolve the optional reference-image bytes via the same `IMAGE_DIR / Path(image_url).name` pattern Stage 3 uses, pass all three into the analyzer / prompt builder. Reuse Stage 3's `_resolve_reference_inputs`-style helper rather than re-implementing.

6. **`backend/src/configs.py`** — three new threshold constants.

### Prompt structure after Stage 7

The prompt loads today's `step2_nutritional_analysis.md` verbatim, then the existing Python helper appends the USER-CONFIRMED data block. Stage 7 inserts the placeholders between the prompt body and the output-contract section so block ordering is explicit:

```
[existing prompt sections: Role & Objective, Theoretical Framework, …]

### Cooking Style / Preparation / Regional Variant
When inferring nutrient numbers, explicitly weigh the dish's cooking
style (deep-fried vs steamed vs grilled), preparation method
(battered, breaded, tempered, raw), and regional variant (North-Indian
vs South-Indian, Hainanese vs Hakka) — reflect those decisions in the
`reasoning_*` fields.

__NUTRITION_DB_BLOCK__
__PERSONALIZED_BLOCK__

### Attribution contract (reasoning_*)
Each `reasoning_*` field is a short string attributing its metric's
value to its source. When a block above is absent, treat it as
authoritatively missing — do NOT cite a Nutrition Database source
that was not provided. An empty `""` for `reasoning_micronutrients`
is acceptable if no micronutrients were found worth reporting.

### Omitted-block rule
If one or both optional blocks are absent from this prompt, rely
on your general dietary knowledge and the attached image(s). Do not
hallucinate a database match.

[USER-CONFIRMED DATA FROM STEP 1 — appended by the Python helper]
[Output Format section — existing schema + new reasoning_* fields]
```

### Rendered block shapes

**Nutrition DB block** (substituted when `nutrition_db_matches.nutrition_matches[0].confidence_score >= 80`):

```markdown
## Nutrition Database Matches (top {N}, with confidence_score)

The following matches were retrieved from a curated nutrition database
(Malaysian / MyFCD / Anuvaad / CIQUAL). Treat them as strong evidence
for `reasoning_*` citations when they align with the query image's
dish. Use them to calibrate your macro estimates; do not copy blindly.

```json
[
  {
    "matched_food_name": "Chicken Rice",
    "source": "malaysian_food_calories",
    "confidence_score": 88.5,
    "calories_kcal": 500,
    "protein_g": 25,
    "carbs_g": 60,
    "fat_g": 15,
    "fiber_g": 1
  },
  …
]
```
```

**Personalization block** (substituted when `personalized_matches[0].similarity_score >= 0.30`):

```markdown
## Personalization Matches (top {N}, this user's prior dishes)

The following are previous uploads by the same user whose caption or
confirmed dish name overlaps this query. Treat them as weaker
evidence than the Nutrition Database above — the user's prior
analysis may itself have been uncertain. When `corrected_step2_data`
is present, it is the user's hand-corrected nutrients and should be
weighted more strongly.

```json
[
  {
    "description": "grilled chicken with rice",
    "similarity_score": 0.88,
    "prior_step2_data": {
      "calories_kcal": 480,
      "protein_g": 22,
      "carbs_g": 55,
      "fat_g": 14,
      "fiber_g": 1
    },
    "corrected_step2_data": null
  },
  …
]
```
```

**Trimmed JSON payload** (confirmed with user 2026-04-19) — the prompt helper does **not** pass the full match dicts through. Stage 5 / Stage 6 store the full shape on `result_gemini`; Stage 7's prompt carries only the fields below.

For DB matches:
```
{matched_food_name, source, confidence_score,
 calories_kcal, protein_g, carbs_g, fat_g, fiber_g}
```
Macro fields pulled out of the source-aware `nutrition_data` (Malaysian / MyFCD / Anuvaad / CIQUAL) via a new `_extract_prompt_macros(match)` helper that is a thin wrapper around `_nutrition_aggregation.extract_single_match_nutrition`.

For personalization matches:
```
{description, similarity_score,
 prior_step2_data: {calories_kcal, protein_g, carbs_g, fat_g, fiber_g} | null,
 corrected_step2_data: {...same five macros if user corrected...} | null}
```

Both trimmed payloads are capped at the top-5 matches (the issue's top-K convention).

### Image-B attachment

Gated strictly on `personalized_matches[0].similarity_score >= THRESHOLD_PHASE_2_2_IMAGE`. Gap band `[0.30, 0.35)`: block included but image B stripped. At-or-above 0.35: both block and image B. Missing-on-disk file: log WARN, degrade to single-image (same pattern as Stage 3).

### Why the gap band (0.30 vs 0.35)

Stage 2 confirmed that `similarity_score` is a max-in-batch relative ranking signal — the top hit is always `1.0`. In a sparse corpus (2-3 prior uploads) every match trivially clears both thresholds. The gap between text-block (0.30) and image-B (0.35) creates a cheap signal: if the top hit barely clears 0.30, Gemini gets a textual hint but not an unframed second image. This matters when the user's corpus has two near-identical past uploads where the BM25 scoring collapses to low absolute numbers despite being the only candidates.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| `result_gemini.nutrition_db_matches` writer | `item_tasks.py::_persist_pre_pro_state` (Stage 5 + Stage 6) | Keep — Stage 7 only reads this key. |
| `result_gemini.personalized_matches` writer | same | Keep. |
| Parallel gather block | `item_tasks.py::_gather_pre_pro_lookups` | Keep — Stage 7 runs after. |
| Stage 5's `extract_single_match_nutrition` | `_nutrition_aggregation.py` | Keep — Stage 7 reuses for the trimmed DB payload. |
| `Step2NutritionalAnalysis` Pydantic schema | `backend/src/service/llm/models.py` | Extend with seven `reasoning_*` fields; existing fields unchanged. |
| `analyze_step2_nutritional_analysis_async` | `backend/src/service/llm/gemini_analyzer.py` | Add `reference_image_bytes=None` kwarg; otherwise unchanged. |
| `get_step2_nutritional_analysis_prompt` | `backend/src/service/llm/prompts.py` | Signature extension + placeholder substitute/strip. |
| `step2_nutritional_analysis.md` prompt body | `backend/resources/` | Append two placeholder lines + cooking-style instruction + attribution-contract section. Rest unchanged. |
| Stage 3 `_resolve_reference_inputs` pattern | `item_step1_tasks.py` | Not imported directly (file-specific) — copy the pattern into a Stage-7 sibling helper in `item_tasks.py`. |
| `IMAGE_DIR` constant | `backend/src/configs.py` | Keep — Stage 7 reuses to resolve `personalized_matches[0].image_url` to disk. |
| Phase 2 persistence / error path | `item_tasks.py` success merge / `persist_phase_error` | Keep — Stage 7 sits inside the existing try-block. |
| `THRESHOLD_PHASE_2_2_SIMILARITY = 0.30` | `configs.py` | Keep — Stage 6 owns it; Stage 7 **reads** it conceptually via the identical `THRESHOLD_PERSONALIZATION_INCLUDE = 0.30` constant. The two values may be the same today but are semantically different knobs (one gates retrieval, the other gates prompt inclusion). |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/resources/step2_nutritional_analysis.md` | No reference-block support; output contract has no `reasoning_*` section. | Append cooking-style instruction + two placeholder lines + attribution-contract instruction + omitted-block rule. |
| `backend/src/service/llm/models.py::Step2NutritionalAnalysis` | 8 response fields + optional micronutrients list. | Add 7 flat `reasoning_*` fields, all `str = Field(default="")`. |
| `backend/src/service/llm/prompts.py::get_step2_nutritional_analysis_prompt` | `(dish_name, components) -> str` | `(dish_name, components, nutrition_db_matches=None, personalized_matches=None) -> str`. Substitute / strip `__NUTRITION_DB_BLOCK__` and `__PERSONALIZED_BLOCK__`; trim JSON payload via two new module-private helpers. |
| `backend/src/service/llm/gemini_analyzer.py::analyze_step2_nutritional_analysis_async` | `(image_path, prompt, model, thinking_budget)` | Add `reference_image_bytes: Optional[bytes] = None`. Second image part appended after the query image when provided. |
| `backend/src/api/item_tasks.py::trigger_step2_analysis_background` | Loads persisted matches implicitly; calls prompt + analyzer with minimal args. | Read `nutrition_db_matches` + `personalized_matches` from the just-persisted `result_gemini`; resolve optional reference-image bytes; plumb all three into the prompt + analyzer calls. |
| `backend/src/configs.py` | Has `THRESHOLD_PHASE_1_1_1_SIMILARITY`, `THRESHOLD_PHASE_2_2_SIMILARITY`. | Adds `THRESHOLD_DB_INCLUDE = 80`, `THRESHOLD_PERSONALIZATION_INCLUDE = 0.30`, `THRESHOLD_PHASE_2_2_IMAGE = 0.35`. |

---

## Implementation Plan

### Key Workflow

No new coroutine — Stage 7 extends the existing try-block of `trigger_step2_analysis_background`. The gather step (Stages 5 + 6) runs first and persists the two match keys; Stage 7 re-reads the record once before the Pro call to resolve the optional image bytes and hand the matches to the prompt builder.

```
trigger_step2_analysis_background(query_id, image_path, dish_name, components)
  │
  ▼ (Stage 5 + Stage 6, unchanged)
nutrition_db_matches, personalized_matches = await _gather_pre_pro_lookups(...)
_persist_pre_pro_state(query_id, nutrition_db_matches, personalized_matches)
  │
  ▼ (NEW — Stage 7 prompt + optional image-B resolution)
reference_image_bytes = _resolve_phase_2_2_image_bytes(personalized_matches)
  ├── if top-1 is None OR similarity_score < THRESHOLD_PHASE_2_2_IMAGE → (None)
  ├── else read IMAGE_DIR / Path(image_url).name
  └── on FileNotFoundError → log WARN, (None)
  │
  ▼
step2_prompt = get_step2_nutritional_analysis_prompt(
    dish_name=dish_name,
    components=components,
    nutrition_db_matches=nutrition_db_matches,
    personalized_matches=personalized_matches,
)
  ├── DB block included only if nutrition_matches[0].confidence_score >= 80
  ├── personalization block included only if personalized_matches[0].similarity_score >= 0.30
  └── both placeholders stripped line-wise when gates fail
  │
  ▼
step2_result = await analyze_step2_nutritional_analysis_async(
    image_path=image_path,
    analysis_prompt=step2_prompt,
    reference_image_bytes=reference_image_bytes,
    gemini_model="gemini-2.5-pro",
    thinking_budget=-1,
)
  │
  ▼ (unchanged success merge)
```

#### To Delete

None.

#### To Update

- `backend/src/api/item_tasks.py::trigger_step2_analysis_background` — re-read the pre-Pro-persisted record to get the two match keys; compute `reference_image_bytes` via the new module-private helper; pass all three into the prompt + analyzer.
- Add module-private `_resolve_phase_2_2_image_bytes(personalized_matches) -> Optional[bytes]` helper in `item_tasks.py`. Parallel to Stage 3's `_resolve_reference_inputs` — single call site; graceful degrade on missing file; `None` on empty/below-threshold match.

#### To Add New

None — the helper stays module-private in the existing file.

---

### Database Schema

**No changes.** Stage 7 is pure read + prompt/schema assembly. The new `reasoning_*` fields live inside the existing `result_gemini.step2_data` JSON blob — no schema change required.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

**No new CRUD.** The pre-Pro-persisted `result_gemini` is re-read via the existing `get_dish_image_query_by_id`. The reference image is read from disk via `Path.read_bytes()` — not CRUD. Stages 5 and 6 already wrote the keys Stage 7 reads.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

#### `backend/src/service/llm/models.py::Step2NutritionalAnalysis`

Add seven flat string fields, all with `default=""`:

```python
class Step2NutritionalAnalysis(BaseModel):
    # ... existing fields unchanged ...
    reasoning_sources: str = Field(
        default="",
        description=(
            "Short string listing which sources drove this analysis "
            "(e.g. 'Nutrition DB: Chicken Rice (malaysian, 88%)', "
            "'User prior: 2026-04-10 upload', or 'LLM-only')."
        ),
    )
    reasoning_calories: str = Field(
        default="",
        description="Rationale for the calories_kcal estimate, citing source if any.",
    )
    reasoning_fiber: str = Field(default="", description="Rationale for fiber_g.")
    reasoning_carbs: str = Field(default="", description="Rationale for carbs_g.")
    reasoning_protein: str = Field(default="", description="Rationale for protein_g.")
    reasoning_fat: str = Field(default="", description="Rationale for fat_g.")
    reasoning_micronutrients: str = Field(
        default="",
        description=(
            "Rationale for the micronutrients list. Empty string is "
            "acceptable when no micronutrients are surfaced."
        ),
    )
```

Gemini structured-output accepts flat schemas only (confirmed by Stage 3 experience) — do **not** nest under a `reasoning` sub-object.

#### `backend/src/service/llm/prompts.py::get_step2_nutritional_analysis_prompt`

New signature:

```python
def get_step2_nutritional_analysis_prompt(
    dish_name: str,
    components: List[Dict[str, Any]],
    nutrition_db_matches: Optional[Dict[str, Any]] = None,
    personalized_matches: Optional[List[Dict[str, Any]]] = None,
) -> str:
```

Body (ordered):

1. Read the .md file as today.
2. Build `db_block_text` — `_render_nutrition_db_block(nutrition_db_matches)` returns either a rendered block string or `""` (gate fails). The regex strip pattern then removes the placeholder line only when the block is `""`.
3. Build `personalized_block_text` — `_render_personalized_block(personalized_matches)` same semantics.
4. Substitute / strip. Reuse Stage 3's regex-strip approach: the placeholder sits on its own line, the strip regex removes it with one trailing newline.
5. Append the existing USER-CONFIRMED DATA block via the current string concatenation.

Module-private helpers:

- `_DB_PLACEHOLDER = "__NUTRITION_DB_BLOCK__"`, `_PERSONA_PLACEHOLDER = "__PERSONALIZED_BLOCK__"`, two matching compiled regex strip patterns.
- `_trim_db_match(match) -> dict` — returns the 8-field trimmed subset described above. Uses `extract_single_match_nutrition(match)` from `_nutrition_aggregation` to get macros in a source-aware way.
- `_trim_personalization_match(match) -> dict` — returns the 4-field trimmed subset described above.
- `_render_nutrition_db_block(matches_dict) -> str` — gate check + JSON-dump + wrap in the markdown heading. Returns `""` when `matches_dict` is falsy, the top match's `confidence_score` is below `THRESHOLD_DB_INCLUDE`, or `nutrition_matches` is empty.
- `_render_personalized_block(matches_list) -> str` — same pattern, gate on `THRESHOLD_PERSONALIZATION_INCLUDE` against the top match's `similarity_score`.

All helpers are sync; the substitute/strip pattern keeps the prompt builder deterministic and easy to unit-test.

#### `backend/src/service/llm/gemini_analyzer.py::analyze_step2_nutritional_analysis_async`

Signature extension:

```python
async def analyze_step2_nutritional_analysis_async(  # pylint: disable=too-many-locals
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1,
    reference_image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
```

Changes inside the body:

- After building the query `image_part`, check `reference_image_bytes`. When set, build a second `types.Part.from_bytes(data=reference_image_bytes, mime_type="image/jpeg")` and extend `contents = [prompt, image_part, reference_part]`. When `None`, `contents = [prompt, image_part]` — identical to today.
- Required-field guard stays the same seven-field list. `reasoning_*` are optional (default `""`); we do **not** extend the guard (user decision 2026-04-19).

Pattern-identical to Stage 3's `analyze_step1_component_identification_async` — the second-image attach is a three-line change.

#### `backend/src/api/item_tasks.py::trigger_step2_analysis_background`

Between the existing pre-Pro-persist call and the prompt-builder call, insert:

```python
# Stage 7: re-read to pick up the persisted matches; resolve optional
# image B from the top-1 personalization match when similarity >= threshold.
record_post_gather = get_dish_image_query_by_id(query_id)
persisted = (record_post_gather.result_gemini or {}) if record_post_gather else {}
nutrition_db_matches = persisted.get("nutrition_db_matches")
personalized_matches = persisted.get("personalized_matches") or []
reference_image_bytes = _resolve_phase_2_2_image_bytes(personalized_matches)
```

Then update the prompt + analyzer calls:

```python
step2_prompt = get_step2_nutritional_analysis_prompt(
    dish_name=dish_name,
    components=components,
    nutrition_db_matches=nutrition_db_matches,
    personalized_matches=personalized_matches,
)
step2_result = await analyze_step2_nutritional_analysis_async(
    image_path=image_path,
    analysis_prompt=step2_prompt,
    gemini_model="gemini-2.5-pro",
    thinking_budget=-1,
    reference_image_bytes=reference_image_bytes,
)
```

New module-private helper `_resolve_phase_2_2_image_bytes(personalized_matches)`:

```python
def _resolve_phase_2_2_image_bytes(
    personalized_matches: List[Dict[str, Any]],
) -> Optional[bytes]:
    if not personalized_matches:
        return None
    top = personalized_matches[0]
    if (top.get("similarity_score") or 0.0) < THRESHOLD_PHASE_2_2_IMAGE:
        return None
    image_url = top.get("image_url")
    if not image_url:
        return None
    disk_path = IMAGE_DIR / Path(image_url).name
    try:
        return disk_path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "Phase 2.3 reference image missing on disk (%s); degrading to single-image: %s",
            disk_path,
            exc,
        )
        return None
```

Imports added to `item_tasks.py`: `from pathlib import Path` (already present), `from src.configs import IMAGE_DIR, THRESHOLD_PHASE_2_2_IMAGE`.

#### `backend/src/configs.py`

```python
# Stage 7 (Phase 2.3) — threshold gates for the Gemini prompt's optional
# reference blocks and for the image-B attach.

# Include the Nutrition Database Matches block only when the top match's
# confidence_score (0-100 scale) clears 80. Tuned against the
# reference-project NDCG eval set; editing invalidates the Stage 9 gate.
THRESHOLD_DB_INCLUDE = 80

# Include the Personalization Matches block only when the top match's
# similarity_score (0-1 scale, max-in-batch normalized) clears 0.30.
# Same value as THRESHOLD_PHASE_2_2_SIMILARITY (Stage 6's retrieval gate)
# by intent; separate knob so prompt-inclusion can be tuned independently
# of retrieval surface.
THRESHOLD_PERSONALIZATION_INCLUDE = 0.30

# Attach the top-1 personalization match's image as a second Gemini input
# (image B) only when its similarity_score clears 0.35. Stricter than
# THRESHOLD_PERSONALIZATION_INCLUDE so the gap band [0.30, 0.35) gives
# Gemini a textual hint without an unframed second image.
THRESHOLD_PHASE_2_2_IMAGE = 0.35
```

Stage 6's `THRESHOLD_PHASE_2_2_SIMILARITY` stays unchanged. The Stage 7 constants are imported wherever they're consumed — none land as function defaults.

#### To Delete

None.

#### To Update

- `backend/resources/step2_nutritional_analysis.md` — append cooking-style instruction, two placeholder lines, attribution-contract instruction, omitted-block rule.
- `backend/src/service/llm/models.py::Step2NutritionalAnalysis` — add seven `reasoning_*` fields.
- `backend/src/service/llm/prompts.py::get_step2_nutritional_analysis_prompt` — new signature + helper functions + substitute/strip regex.
- `backend/src/service/llm/gemini_analyzer.py::analyze_step2_nutritional_analysis_async` — `reference_image_bytes` parameter.
- `backend/src/api/item_tasks.py::trigger_step2_analysis_background` — re-read record, resolve image bytes, plumb into prompt + analyzer.
- `backend/src/api/item_tasks.py` — new `_resolve_phase_2_2_image_bytes` helper.
- `backend/src/configs.py` — three new thresholds.

#### To Add New

None — every change lands in an existing file.

---

### API Endpoints

None. Stage 7 does not add routes or change request/response contracts. `GET /api/item/{id}` already returns the full `result_gemini`; the new `reasoning_*` keys on `step2_data` ride along.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. Extensions to existing files (`test_prompts.py`, `test_gemini_analyzer.py`, `test_item_tasks.py`). No new test files.

**Unit tests — prompt builder (`backend/tests/test_prompts.py` — extend):**

- `test_step2_prompt_strips_both_placeholders_on_no_matches` — `nutrition_db_matches=None, personalized_matches=None`; assert `__NUTRITION_DB_BLOCK__` and `__PERSONALIZED_BLOCK__` absent; `## Nutrition Database Matches` and `## Personalization Matches` also absent from the result.
- `test_step2_prompt_substitutes_db_block_when_confidence_ge_threshold` — fixture `nutrition_matches[0].confidence_score = 85`; assert the block appears with a trimmed JSON payload that includes `matched_food_name`, `source`, `confidence_score`, macro fields — AND does NOT include `raw_bm25_score` / full `raw_data`.
- `test_step2_prompt_strips_db_block_when_confidence_below_threshold` — `confidence_score = 75`; block absent.
- `test_step2_prompt_strips_db_block_when_nutrition_matches_empty` — `nutrition_matches: []`; block absent.
- `test_step2_prompt_substitutes_personalization_block_when_similarity_ge_threshold` — top match `similarity_score = 0.55`; block present; trimmed payload includes `description`, `similarity_score`, `prior_step2_data` macros; does NOT include `image_url` / `query_id`.
- `test_step2_prompt_strips_personalization_block_when_top_below_threshold` — `similarity_score = 0.25`; block absent.
- `test_step2_prompt_carries_corrected_step2_data_when_present` — one match has `corrected_step2_data` set; assert it surfaces in the rendered JSON.
- `test_step2_prompt_trims_to_top_5_matches` — pass a list of 10 personalization matches; assert the rendered block JSON has exactly 5 entries.
- `test_step2_prompt_db_block_precedes_personalization_block` — both blocks included; assert the DB block appears first in the rendered prompt (index check).
- `test_step2_prompt_handles_malformed_match_payload_defensively` — missing keys / unexpected types; the renderer should emit safe fallbacks (e.g. `null` for absent nutrients) rather than raising.

**Unit tests — analyzer (`backend/tests/test_gemini_analyzer.py` — extend):**

- `test_analyze_step2_sends_single_image_when_no_reference_bytes` — assertion parallel to the Phase 1 test; `reference_image_bytes=None` → `len(contents) == 2`.
- `test_analyze_step2_sends_two_images_when_reference_bytes_provided` — `reference_image_bytes=b"ref-bytes"` → `len(contents) == 3`.
- `test_analyze_step2_preserves_image_order_query_first_reference_second` — index 1 = query bytes, index 2 = reference bytes.
- `test_analyze_step2_does_not_require_reasoning_fields` — Gemini returns a response with empty-string `reasoning_*` fields; assert the analyzer does not raise; the result dict carries the keys with `""` values.

**Unit tests — background task (`backend/tests/test_item_tasks.py` — extend):**

- `test_phase2_task_reads_persisted_matches_and_passes_to_prompt_builder` — fixture `result_gemini` already carries `nutrition_db_matches` + `personalized_matches`; assert the prompt builder was called with both.
- `test_phase2_task_resolves_image_bytes_when_similarity_above_threshold` — personalization top-1 `similarity_score = 0.50`, matching file on `IMAGE_DIR`; assert `analyze_step2_nutritional_analysis_async` called with `reference_image_bytes = <file bytes>`.
- `test_phase2_task_skips_image_bytes_when_similarity_below_threshold` — top-1 `similarity_score = 0.32`; assert `reference_image_bytes=None` passed to analyzer. Block is still substituted by the prompt builder (tested separately) so the test is narrowly scoped to the image-bytes kwarg.
- `test_phase2_task_skips_image_bytes_when_file_missing_and_logs_warn` — top-1 `similarity_score = 0.60`, file not on disk; assert analyzer called with `None` AND a WARN log line mentions `"reference image missing"`.
- `test_phase2_task_skips_image_bytes_when_no_personalized_matches` — `personalized_matches=[]`; assert `reference_image_bytes=None`, no warn.
- `test_phase2_task_persists_reasoning_fields_from_step2_result` — monkeypatched analyzer returns `reasoning_sources="Nutrition DB"` etc.; assert the final `result_gemini.step2_data` carries the seven reasoning keys.

**Pre-commit loop (mandatory):**

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix lint / line-count / complexity issues. `prompts.py` will grow ~100 lines with the block renderers — consider extracting `_trim_db_match` + `_trim_personalization_match` + `_render_*` into `_step2_blocks.py` if line-count pressure hits. `item_tasks.py` gets ~20 lines more — well under cap.
3. Re-run. Repeat until clean.

**Acceptance check from the issue's "done when":**

- A query with a high-confidence DB match produces a `step2_data` whose numbers differ from the no-DB baseline AND whose `reasoning_*` strings cite the DB source.
- Below-threshold queries still work and return non-empty `reasoning_*` explaining the LLM-only path.
- Chrome Test 1 (high-confidence DB) and Test 5 (cold-start) are the end-to-end acceptance gates.

#### To Delete

None.

#### To Update

- `backend/tests/test_prompts.py` — append ~10 tests for Stage 7 block gating.
- `backend/tests/test_gemini_analyzer.py` — append ~4 tests for the reference-image kwarg.
- `backend/tests/test_item_tasks.py` — append ~6 tests for the persisted-matches read path.

#### To Add New

None.

---

### Frontend

None. Stage 7 ships no UI. The Step 2 view renders existing macros + rationale; the new `reasoning_*` fields are invisible until Stage 8 adds the ReasoningPanel component.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/nutritional_analysis.md`:
  - Flip the two "consulted silently" paragraphs added in Stages 5/6 to active language. The system now:
    - Consults the curated nutrition database and surfaces high-confidence matches to the AI as evidence when it runs the nutrition analysis.
    - Consults the user's own personalization history and surfaces strong prior matches (including an optional second photo from the user's past dish) as a hint.
  - Mention the new "reasoning" attribution surface: the AI now returns a short rationale per metric. These strings will drive Stage 8's "Why these numbers?" panel; for now they're stored but not yet shown.
  - Guardrails paragraph: when matches are weak or absent the AI falls back to its own knowledge + the image, explicitly flagging the fallback in the reasoning text.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/nutritional_analysis.md`:
  - Add **Phase 2.3 — Reference-Assisted Prompt (Stage 7)** sub-section documenting:
    - Prompt placeholder strategy (`__NUTRITION_DB_BLOCK__`, `__PERSONALIZED_BLOCK__`); symmetric with Stage 3's `__REFERENCE_BLOCK__`.
    - The three thresholds and their scales.
    - The trimmed JSON payload shape for each block.
    - Block ordering rule (DB first, personalization second).
    - The `reasoning_*` additions to the Step 2 schema (7 new fields, all `default=""`).
    - The image-B attach rule (top-1 personalization similarity ≥ 0.35).
    - Graceful-degrade paths: missing file → single image; malformed matches payload → safe fallbacks.
  - Extend the existing Pipeline ASCII diagram with the placeholder-resolution + image-bytes-resolution steps between the pre-Pro persist and the analyzer call.
  - Update the Component Checklist:
    - `[x] Stage 7 — prompt builder accepts optional matches + threshold-gates the two blocks`
    - `[x] Stage 7 — step2_nutritional_analysis.md adds `__NUTRITION_DB_BLOCK__` + `__PERSONALIZED_BLOCK__` placeholders`
    - `[x] Stage 7 — Step2NutritionalAnalysis adds 7 reasoning_* fields`
    - `[x] Stage 7 — analyzer accepts reference_image_bytes`
    - `[x] Stage 7 — trigger_step2_analysis_background resolves image bytes and plumbs matches through`
    - `[x] Stage 7 — THRESHOLD_DB_INCLUDE / THRESHOLD_PERSONALIZATION_INCLUDE / THRESHOLD_PHASE_2_2_IMAGE`
- **Update** `docs/technical/dish_analysis/nutrition_db.md`:
  - Flip `[ ] Stage 7` to `[x]` on the Component Checklist.
  - Extend the "Downstream consumers" section with a one-line note: "Stage 7 prompt gates inclusion on `confidence_score >= THRESHOLD_DB_INCLUDE (80)`".
- **Update** `docs/technical/dish_analysis/personalized_food_index.md`:
  - Flip `[ ]` → `[x]` on Stage 7 row if one exists; otherwise add a new `[x] Stage 7 — ...` row.
  - Note the dual-threshold: block at 0.30, image-B at 0.35.

#### API Documentation (`docs/api_doc/`)

No changes — Stage 7 adds no endpoints. The response shape grows seven optional string keys which is a non-breaking addition. Project does not yet ship `docs/api_doc/`.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/nutritional_analysis.md` — flip the silent paragraphs to active.
- `docs/technical/dish_analysis/nutritional_analysis.md` — new Phase 2.3 sub-section + Pipeline extension + Component Checklist.
- `docs/technical/dish_analysis/nutrition_db.md` — flip Stage 7 row + downstream-consumer note.
- `docs/technical/dish_analysis/personalized_food_index.md` — flip Stage 7 row + dual-threshold note.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks.md`. 10 tests, 5 desktop + 5 mobile. Covers:

1. High-confidence DB match → block injected, `reasoning_*` cites DB.
2. Low-confidence DB match → block stripped, `reasoning_*` reflects LLM-only.
3. Warm personalization ≥ 0.35 → block + image B attached; `reasoning_*` cites user's prior.
4. Gap band (0.30–0.35) → block injected, image B omitted. Marked optional (manual-setup cost).
5. Both absent (cold-start + obscure dish) → both placeholders stripped; all `reasoning_*` populated with LLM-only rationale.

Scope caveats:
- Temporary backend log line in `gemini_analyzer.py` to inspect image-part count + block presence. Revert before commit.
- Tests 4 and 8 need a crafted corpus or temporary `THRESHOLD_PHASE_2_2_IMAGE` override. Mark as skippable.
- 10 tests × ~5–10 s Gemini Pro wall-clock ≈ 1–2 min + Pro pricing per run.
- Placeholder usernames (no `docs/technical/testing_context.md`).

Execution flow: `feature-implement-full` invokes `chrome-test-execute` after Stage 7 lands.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260419_1053_stage7_phase2_3_gemini_threshold_gated_blocks.md` (already written).

---

## Dependencies

- **Stage 5** — `result_gemini.nutrition_db_matches` is the source Stage 7 reads.
- **Stage 6** — `result_gemini.personalized_matches` is the source Stage 7 reads AND the source of the optional image-B bytes.
- **Stage 2** — `reference_image.description` flowed into Stage 6 queries; not touched here.
- **Stage 3** — placeholder-substitution pattern (`_REFERENCE_STRIP_RE` in `prompts.py`) is the precedent Stage 7 follows.
- **`_nutrition_aggregation.py::extract_single_match_nutrition`** — reused by `_trim_db_match` to get source-aware macros for the prompt's DB block.
- **Existing Phase 2 pipeline** — `trigger_step2_analysis_background`, `get_step2_nutritional_analysis_prompt`, `analyze_step2_nutritional_analysis_async`, `persist_phase_error`. Signatures extended; no new functions in the orchestration layer.
- **No new external libraries.**
- **No schema changes.**

---

## Resolved Decisions

- **JSON payload for the two blocks is trimmed, not full** (confirmed with user 2026-04-19). DB block carries `matched_food_name, source, confidence_score` + five macros. Personalization block carries `description, similarity_score, prior_step2_data (5 macros), corrected_step2_data (5 macros when present)`. Drops `raw_bm25_score`, full `raw_data`, `image_url`, `query_id`, `nutrition_data` verbatim. Roughly 300–500 tokens per block instead of 2–5 k. Faster, less prompt noise, outbound prompts stay readable in backend.log.
- **`reasoning_*` fields stay optional (default `""`)** (confirmed with user 2026-04-19). The analyzer's required-field guard is unchanged — still the seven macro/identity fields. Empty reasoning strings are rendered as "No rationale provided" by Stage 8's future panel.
- **`THRESHOLD_DB_INCLUDE = 80`** (0–100 scale, compared against `confidence_score`). Issue-pinned. Stage 5's confidence formula caps at 0.95 (95 on the 100-scale), so 80 is a sensible cutoff that excludes low-confidence BM25 noise without starving the prompt of evidence.
- **`THRESHOLD_PERSONALIZATION_INCLUDE = 0.30`** equals `THRESHOLD_PHASE_2_2_SIMILARITY` by intent, not by accident. Separate knobs so prompt-inclusion can be tuned independently of retrieval surface (e.g. Stage 6 could retrieve at 0.30 but Stage 7 could later tighten block inclusion to 0.50 without re-deploying Stage 6).
- **`THRESHOLD_PHASE_2_2_IMAGE = 0.35`** deliberately higher than the block-include threshold. Creates a `[0.30, 0.35)` gap band where Gemini gets textual evidence but no unframed second image — tested in Chrome Test 4.
- **DB block precedes personalization block in the prompt** (decision recorded by the planner). The curated nutrition database is the more authoritative source; user history is weaker evidence per the prompt's attribution contract. Ordering is explicit in the .md so future prompt edits cannot accidentally swap.
- **Placeholder-substitution strategy mirrors Stage 3** (decision recorded by the planner). Each placeholder lives on its own line; the strip regex (`re.compile(r"^[ \t]*PLACEHOLDER[ \t]*\n?", re.M)`) removes exactly that line. Prompt rendering is deterministic and unit-testable.
- **Stage 7 reads matches via a fresh DB re-read, not via closure** (decision recorded by the planner). The gather step (Stages 5 + 6) persists onto `result_gemini`; Stage 7 re-reads to pick them up. Costs one extra SELECT per Phase 2 run (~1 ms) and cleanly separates persistence from consumption — a retry that re-enters `trigger_step2_analysis_background` can see a different persisted state (e.g. if a concurrent Stage 8 correction landed between runs).
- **`_resolve_phase_2_2_image_bytes` is module-private in `item_tasks.py`** (decision recorded by the planner). Stage 3's equivalent helper lives in `item_step1_tasks.py`; both stages own their reference-image resolution since the semantics differ (Stage 3 reads Phase 1.1.1's full reference dict; Stage 7 reads Phase 2.2's top-1 match). Duplicating ~20 lines beats premature abstraction.

## Open Questions

None — all decisions resolved 2026-04-19. Ready for implementation.
