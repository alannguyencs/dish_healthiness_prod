# Stage 3 — Phase 1.1.2: Two-Image, Reference-Assisted Component ID

**Feature**: Consume Stage 2's `result_gemini.reference_image` in the Step 1 Pro call. When a full reference is available (image file on disk + `prior_step1_data` non-null), Phase 1.1.2 now sends Gemini 2.5 Pro **two image parts** plus an injected "Reference results (HINT ONLY)" block carrying the referenced dish's prior analysis. Cold start, null `prior_step1_data`, and missing-image-on-disk all degrade to today's single-image behavior.
**Plan Created:** 2026-04-18
**Status:** Plan
**Reference**:
- [Issues — 260415, Stage 3](../issues/260415.md)
- [Discussion — Food DB investigation & end-to-end redesign](../discussion/260418_food_db.md)
- [Plan — Stage 2 Phase 1.1.1](./260418_stage2_phase1_1_1_fast_caption.md) (the producer of `result_gemini.reference_image`)
- [Abstract — Component Identification](../abstract/dish_analysis/component_identification.md)
- [Technical — Component Identification](../technical/dish_analysis/component_identification.md)
- [Chrome Test Spec — 260418_2318](../chrome_test/260418_2318_stage3_phase1_1_2_reference_assisted_component_id.md)

---

## Problem Statement

1. Stage 2 wired the per-user retrieval: every upload now has `result_gemini.reference_image` populated (or null) before the Step 1 Pro call runs. But Phase 1.1.2 still ignores that key — the Pro prompt is identical to the cold-start prompt and only one image part is attached. The retrieval costs a Gemini Flash call per upload that currently buys nothing.
2. The end-to-end workflow in `docs/discussion/260418_food_db.md` expects Phase 1.1.2 to consume both (a) the reference image as a second `types.Part.from_bytes`, and (b) the referenced dish's `prior_step1_data` as an explicit "Reference results (HINT ONLY)" block in the prompt. The prompt must frame the reference as a hint the LLM is allowed to disagree with, never as ground truth.
3. Four degrade paths must fall back cleanly to today's single-image behavior:
   - Cold-start user: `reference_image` is null → no change from today.
   - `reference_image.prior_step1_data` is null (referenced dish's Phase 1.1.2 never completed, Stage 2 tolerates this) → skip both image and text block, degrade to single-image (user decision Option B, 2026-04-18).
   - Reference image file missing on disk (slot-replace race, manual cleanup) → log WARN, degrade to single-image.
   - Retry after a Phase 1.1.2 failure: reference already persisted on the record → re-run the Pro call with the saved reference, not a fresh retrieval.
4. Stage 3 is the first prompt / analyzer surface change in the new pipeline. The prompt template changes need a reversible substitution scheme (the prompt lives in `backend/resources/step1_component_identification.md`, not hard-coded) so future maintainers can edit the block independently of the Python helper.

---

## Proposed Solution

Four artifacts change, none added:

1. **`backend/resources/step1_component_identification.md`** — insert a single placeholder token `__REFERENCE_BLOCK__` at the end of the `Task Description` section (before `Output Format`). Keep the placeholder on its own line so the "strip" path removes exactly the line, leaving no empty section behind.
2. **`backend/src/service/llm/prompts.py::get_step1_component_identification_prompt(reference=None)`** — read the .md, then:
   - When `reference is None`: regex-strip the `__REFERENCE_BLOCK__` line (and any surrounding blank lines) → return the prompt with no trace of a reference section.
   - When `reference` is a dict with `prior_step1_data`: render a Markdown block from that data (dish name, components, serving sizes, predicted servings) → substitute.
   - When `reference` is a dict with `prior_step1_data is None`: treat as `reference=None` (strip). This matches the caller's contract (the caller only passes a `reference` dict when `prior_step1_data` is non-null; this branch is defensive).
3. **`backend/src/service/llm/gemini_analyzer.py::analyze_step1_component_identification_async(..., reference_image_bytes=None)`** — accept an optional `bytes` argument. When provided, build a second `types.Part.from_bytes` and append to `contents` **after** the query image (so the query image remains "image A"). When `None`, the contents list is single-image, identical to today.
4. **`backend/src/api/item_step1_tasks.py::analyze_image_background`** — read the already-persisted `result_gemini.reference_image` from the record after Phase 1.1.1 writes it (or on retry, from the DB), resolve the disk path via `IMAGE_DIR / Path(image_url).name`, read bytes (graceful-degrade on `FileNotFoundError`), and pass both `reference_image_bytes` and `reference` into the Pro call helpers.

### Decision matrix for the four degrade paths

| Path                                              | `reference_image` persisted | File on disk | `prior_step1_data` | Image parts sent | Prompt block     |
|---------------------------------------------------|-----------------------------|--------------|--------------------|------------------|------------------|
| Cold-start                                        | `null`                      | —            | —                  | 1                | Stripped         |
| Below-threshold match (no ref)                    | `null`                      | —            | —                  | 1                | Stripped         |
| Fast-caption failed                               | `null`                      | —            | —                  | 1                | Stripped         |
| Warm-start, full reference                        | populated                   | present      | present            | **2**            | **Substituted**  |
| Warm-start, `prior_step1_data` null (Option B)    | populated                   | present      | `null`             | 1                | Stripped         |
| Warm-start, image file missing                    | populated                   | missing      | any                | 1                | Stripped + WARN  |
| Retry-step1 after Phase 1.1.2 failure             | preserved from prior attempt | present (usually) | present     | 2                | Substituted      |

The matrix is implemented at a single call-site inside `analyze_image_background` so every degrade path is auditable in one place.

### Rendered reference block

The substituted block (written by `prompts.py`):

```markdown
## Reference results (HINT ONLY — may or may not match)

The user has uploaded a similar dish before. The **image attached after the query image is the prior dish**, and the analysis below is what we produced for it last time. Use this ONLY as a hint — the two dishes may differ in cuisine, preparation, or portion. If the query image disagrees, trust the query image.

**Prior dish name:** {prior.dish_predictions[0].name}

**Prior components (name · serving sizes · predicted servings):**
- {c.component_name} · {serving_sizes comma-joined} · {c.predicted_servings}
- …
```

Only fields that exist on `prior_step1_data` are rendered. If `dish_predictions` is empty or absent, the dish-name line is omitted. If `components` is empty, the components list is omitted. The block itself is not rendered if both are empty (defensive; Stage 2 should already not surface a match whose `prior_step1_data` is structurally empty, but the Python builder belt-and-suspenders this).

### Why a placeholder token in the .md, not append-at-end

- Symmetric with Stage 7 (Phase 2.3) which will also substitute placeholders at specific positions.
- The block belongs logically **before** the `Output Format` section — placing it after the output schema would visually confuse the "HINT ONLY" framing with the required JSON shape. A placeholder anchors the insertion point explicitly.
- The strip-line regex handles the empty case cleanly; the alternative (string-concat at end when reference is provided) leaves no insertion-point anchor if the team later moves sections around.

---

## Current Implementation Analysis

### What Exists (keep as-is)

| Component | File | Status |
|-----------|------|--------|
| Phase 1.1.1 orchestrator | `backend/src/service/personalized_reference.py` | Keep — writes `result_gemini.reference_image` before this stage runs |
| `fast_caption.py` | `backend/src/service/llm/fast_caption.py` | Keep — orthogonal to Stage 3 |
| `analyze_image_background` Phase 1.1.1 call + pre-Pro persist | `backend/src/api/item_step1_tasks.py` | Keep — the pre-Pro persist is the guarantee Stage 3 relies on for retry idempotency |
| Stage 0 personalization CRUD + index | `backend/src/crud/crud_personalized_food.py`, `backend/src/service/personalized_food_index.py` | Keep — unchanged |
| Retry endpoint | `backend/src/api/item_retry.py::retry_step1_analysis` | Keep — still calls `analyze_image_background` unchanged |
| Upload endpoints | `backend/src/api/date.py` | Keep — unchanged; the retrieval runs inside the background task |
| `Step1ComponentIdentification` Pydantic schema | `backend/src/service/llm/models.py` | Keep — Stage 3 does not change the response shape |
| Frontend Step 1 editor, polling hook, error card | `frontend/src/pages/ItemV2.jsx`, `useItemPolling.js`, `PhaseErrorCard.jsx` | Keep — no UI changes in this stage |
| `IMAGE_DIR` constant | `backend/src/configs.py` | Keep — used to resolve disk paths from `/images/{name}` URLs (same pattern as `item_retry.py`) |

### What Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/resources/step1_component_identification.md` | Single-image prompt; no reference section. | Insert `__REFERENCE_BLOCK__` placeholder line at the end of the Task Description section, before the Output Format section. |
| `backend/src/service/llm/prompts.py::get_step1_component_identification_prompt` | Zero-arg function returning the prompt verbatim. | Accept optional `reference=None`. Substitute the placeholder with a rendered block when `reference['prior_step1_data']` is non-null; strip the placeholder line otherwise. |
| `backend/src/service/llm/gemini_analyzer.py::analyze_step1_component_identification_async` | Accepts `image_path`, `analysis_prompt`, model, thinking_budget. Attaches one image part. | Adds `reference_image_bytes=None`. When provided, appends a second `types.Part.from_bytes` to `contents` after the query image. |
| `backend/src/api/item_step1_tasks.py::analyze_image_background` | Calls Phase 1.1.1, persists `reference_image`, then calls the Pro analyzer with the prompt-loader output. | Reads the just-persisted `reference_image` off the record, resolves / reads the reference image bytes (graceful degrade on missing file), passes both `reference` and `reference_image_bytes` into the prompt builder + analyzer. |
| `docs/technical/dish_analysis/component_identification.md` | Describes Phase 1.1.1 (Stage 2) + the pipeline. | Adds a "Phase 1.1.2 — Reference-Assisted Component ID" sub-sub-section under the Architecture block; updates the pipeline ASCII to show two image parts when applicable; extends the Component Checklist. |
| `docs/abstract/dish_analysis/component_identification.md` | "Personalization (silent in this stage)" paragraph added in Stage 2. | Flip the framing: "Personalization (now active): when a similar prior dish is retrieved, its image + prior analysis are passed to the AI as a hint; accuracy improves on repeat dishes." |

---

## Implementation Plan

### Key Workflow

Phase 1.1.2 gains a pre-call resolution step that turns the persisted `reference_image` dict into concrete `reference_image_bytes` + `reference` arguments for the analyzer and prompt builder. All branching lives in `analyze_image_background`.

```
analyze_image_background(query_id, file_path, retry_count=0)
  │
  ▼
... (Phase 1.1.1 runs first — unchanged from Stage 2) ...
  │
  ▼
record = get_dish_image_query_by_id(query_id)
reference = (record.result_gemini or {}).get("reference_image")  # may be None
  │
  ▼
reference_image_bytes, effective_reference = _resolve_reference_inputs(reference)
  │
  ├── if reference is None: return (None, None)             ← cold start / below-threshold / caption failure
  │
  ├── image_url = reference["image_url"]
  │   disk_path = IMAGE_DIR / Path(image_url).name
  │   try:
  │       bytes_ = disk_path.read_bytes()
  │   except (FileNotFoundError, OSError):
  │       log WARN "Phase 1.1.2 reference image missing; degrading to single-image"
  │       return (None, None)                                ← missing-on-disk
  │
  ├── if reference.get("prior_step1_data") is None:
  │       return (None, None)                                ← Option B: degrade on null prior (user decision)
  │
  └── return (bytes_, reference)                             ← full reference path
  │
  ▼
step1_prompt = get_step1_component_identification_prompt(reference=effective_reference)
step1_result = analyze_step1_component_identification_async(
    image_path=file_path,
    analysis_prompt=step1_prompt,
    reference_image_bytes=reference_image_bytes,
    gemini_model="gemini-2.5-pro",
    thinking_budget=-1,
)
  │
  ▼
... (merge into result_gemini — unchanged) ...
```

The new helper `_resolve_reference_inputs` is module-private (leading underscore) and lives inside `item_step1_tasks.py`. It is small enough (~20 lines) that extracting it to a separate module buys nothing.

#### To Delete

None.

#### To Update

- `backend/src/api/item_step1_tasks.py::analyze_image_background` — insert the `_resolve_reference_inputs(reference)` call between the post-Phase-1.1.1 re-read (or the record_pre read on the retry short-circuit path) and the Pro analyzer call. Pass both outputs into `get_step1_component_identification_prompt` and `analyze_step1_component_identification_async`.
- Add module-private `_resolve_reference_inputs(reference) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]` inside the same file.

#### To Add New

None.

---

### Database Schema

**No changes.** Stage 3 does not touch the DB. All reads are off `DishImageQuery.result_gemini.reference_image` (populated by Stage 2) and disk-backed image files (populated by `date.py::_process_and_save_image`).

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### CRUD

No new CRUD. Stage 3 is a pure read + call-site plumbing change:

- `crud_food_image_query.get_dish_image_query_by_id(query_id)` — already exists; called once more inside `analyze_image_background` to read back the `reference_image` Phase 1.1.1 just persisted. This read is necessary because the pre-Pro write may include a `reference_image` that differs from what is cached in the `record_pre` object at the top of the task.

  Alternative considered: pass `reference` directly from the Phase 1.1.1 return path as a local variable, skipping the re-read. Rejected because the retry short-circuit path doesn't call `resolve_reference_for_upload` (so there is no local variable); the re-read unifies both paths.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Services

#### `backend/src/service/llm/prompts.py`

Signature change:

```python
def get_step1_component_identification_prompt(
    reference: Optional[Dict[str, Any]] = None,
) -> str:
```

- **Contract**: `reference` is either `None` (no reference available) or a dict matching the shape of `result_gemini.reference_image`. Only `reference["prior_step1_data"]` is consumed by the prompt builder; other fields are ignored at this layer.
- Behavior:
  - Read `backend/resources/step1_component_identification.md` as today.
  - If `reference is None` or `reference.get("prior_step1_data")` is falsy (None or empty dict): strip the line containing `__REFERENCE_BLOCK__` (and one trailing newline so no blank gap remains).
  - Else: render the block described in **Proposed Solution** and substitute for the placeholder line.
  - `FileNotFoundError` on the .md file continues to propagate (unchanged behavior).

Rendering helper (module-private, ~15 lines):

```python
def _render_reference_block(prior_step1_data: Dict[str, Any]) -> str:
    lines = ["## Reference results (HINT ONLY — may or may not match)", ""]
    lines.append(
        "The user has uploaded a similar dish before. The **image attached after "
        "the query image is the prior dish**, and the analysis below is what we "
        "produced for it last time. Use this ONLY as a hint — the two dishes may "
        "differ in cuisine, preparation, or portion. If the query image disagrees, "
        "trust the query image."
    )
    dish_predictions = prior_step1_data.get("dish_predictions") or []
    if dish_predictions and dish_predictions[0].get("name"):
        lines += ["", f"**Prior dish name:** {dish_predictions[0]['name']}"]
    components = prior_step1_data.get("components") or []
    if components:
        lines += ["", "**Prior components (name · serving sizes · predicted servings):**"]
        for c in components:
            name = c.get("component_name", "Unknown")
            sizes = ", ".join(c.get("serving_sizes") or [])
            servings = c.get("predicted_servings", 1.0)
            lines.append(f"- {name} · {sizes} · {servings}")
    return "\n".join(lines)
```

#### `backend/src/service/llm/gemini_analyzer.py`

Signature change:

```python
async def analyze_step1_component_identification_async(
    image_path: Path,
    analysis_prompt: str,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1,
    reference_image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
```

- Behavior:
  - Build the primary `image_part` from `image_path` as today.
  - When `reference_image_bytes is not None`: build a second `types.Part.from_bytes(data=reference_image_bytes, mime_type="image/jpeg")` and extend `contents` to `[analysis_prompt, image_part, reference_part]`. Order matters — the prompt's "image B is the prior dish" framing relies on the query image landing first.
  - When `reference_image_bytes is None`: contents stays `[analysis_prompt, image_part]` — identical to today.
  - No change to Gemini config (temperature 0, structured schema, thinking_budget). No change to return shape.

#### `backend/src/api/item_step1_tasks.py`

Add module-private helper:

```python
def _resolve_reference_inputs(
    reference: Optional[Dict[str, Any]],
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
    """
    Turn a persisted result_gemini.reference_image dict into concrete
    (reference_image_bytes, reference) arguments for Phase 1.1.2.

    Returns (None, None) on any of the four degrade paths:
      - reference is None (cold start / below threshold / caption failure)
      - reference.image_url resolves to a missing file on disk
      - reference.prior_step1_data is None (Option B per user decision 2026-04-18)
      - reference.prior_step1_data is an empty dict (defensive)
    """
```

Inside `analyze_image_background`, after the Phase 1.1.1 block and before the Pro call, re-read the record and resolve:

```python
record_after_1_1_1 = get_dish_image_query_by_id(query_id)
reference_from_blob = (
    (record_after_1_1_1.result_gemini or {}).get("reference_image")
    if record_after_1_1_1
    else None
)
reference_image_bytes, effective_reference = _resolve_reference_inputs(reference_from_blob)
```

Then the existing prompt-loader and analyzer calls become:

```python
step1_prompt = get_step1_component_identification_prompt(reference=effective_reference)
step1_result = await analyze_step1_component_identification_async(
    image_path=file_path,
    analysis_prompt=step1_prompt,
    reference_image_bytes=reference_image_bytes,
    gemini_model="gemini-2.5-pro",
    thinking_budget=-1,
)
```

#### Configs

No change. `IMAGE_DIR` is already defined for `date.py` and `item_retry.py`.

#### To Delete

None.

#### To Update

- `backend/src/service/llm/prompts.py` — add `reference=None` parameter + `_render_reference_block` helper; add placeholder-strip logic.
- `backend/src/service/llm/gemini_analyzer.py` — add `reference_image_bytes=None` parameter + conditional second image part.
- `backend/src/api/item_step1_tasks.py` — add `_resolve_reference_inputs` helper; re-read record and plumb reference + bytes through the Pro call.
- `backend/resources/step1_component_identification.md` — insert `__REFERENCE_BLOCK__` placeholder line before the `Output Format` section.

#### To Add New

None.

---

### API Endpoints

None. Stage 3 exposes no new routes and does not change the contract of any existing endpoint. All observable changes ride on `result_gemini.step1_data` (improved accuracy) plus backend logs (image_parts count). Retry endpoint is unchanged.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Testing

Test location: `backend/tests/`. No new test files are required; all changes are extensions to existing files:

**Unit tests — prompt builder (`backend/tests/test_prompts.py` — NEW file if absent, else append):**

Check whether the file exists first. If not, create it with the standard header + skeleton. Tests to add:

- `test_get_step1_prompt_strips_placeholder_when_reference_is_none` — call with no args; assert `__REFERENCE_BLOCK__` is not in the returned string AND the string does not contain a stray `## Reference results` heading AND the string length is reasonable (within ~100 chars of the raw .md minus the placeholder line).
- `test_get_step1_prompt_strips_placeholder_when_prior_step1_data_is_none` — call with `reference={"prior_step1_data": None}`; same assertions as above.
- `test_get_step1_prompt_substitutes_block_with_full_prior_data` — call with a full `prior_step1_data` payload; assert the returned string contains the dish name line, the components header, and every component's name + joined serving sizes + predicted_servings.
- `test_get_step1_prompt_omits_dish_name_line_when_dish_predictions_empty` — `prior_step1_data={"dish_predictions": [], "components": [...]}`; assert the components block is present but no "Prior dish name:" line.
- `test_get_step1_prompt_omits_components_block_when_empty` — `prior_step1_data={"dish_predictions": [{"name": "X"}], "components": []}`; assert dish-name line present but no "Prior components" heading.
- `test_get_step1_prompt_handles_missing_component_fields_defensively` — one component missing `serving_sizes`; assert no `KeyError`; the component line renders with an empty serving-sizes section.

**Unit tests — analyzer (`backend/tests/test_gemini_analyzer.py` — NEW file if absent, else append):**

Patch `google.genai.Client` with a `_patch_client(...)` fixture as in `test_fast_caption.py`. Tests to add:

- `test_analyze_step1_sends_single_image_when_no_reference_bytes` — `reference_image_bytes=None`; assert the captured `contents` argument has exactly 2 items (prompt + 1 image part).
- `test_analyze_step1_sends_two_images_when_reference_bytes_provided` — pass `reference_image_bytes=b"fake-ref"`; assert `contents` has 3 items (prompt + 2 image parts) AND the second image part's `mime_type == "image/jpeg"`.
- `test_analyze_step1_preserves_order_query_image_first_then_reference` — the query image bytes must land at index 1, reference at index 2. (Patterns can assert `contents[1].inline_data.data == b"query-bytes"` and `contents[2].inline_data.data == b"fake-ref"`.)

**Unit tests — background task (`backend/tests/test_item_step1_tasks.py` — append):**

Four new end-to-end tests covering the decision matrix:

- `test_analyze_image_background_passes_single_image_on_cold_start` — `reference_image=None` on the record after Phase 1.1.1. Assert the Pro analyzer was called with `reference_image_bytes=None` and the prompt builder with `reference=None`. (Patch the analyzer + prompt builder and inspect the captured kwargs.)
- `test_analyze_image_background_passes_two_images_on_full_warm_start` — `reference_image` with `prior_step1_data` populated AND image file exists on disk (use `tmp_path` + `monkeypatch.setattr(item_step1_tasks, "IMAGE_DIR", tmp_path)`). Assert analyzer called with `reference_image_bytes=<file bytes>` and prompt builder with `reference` whose `prior_step1_data` matches.
- `test_analyze_image_background_degrades_when_prior_step1_data_is_null` — `reference_image` populated, `prior_step1_data=None`. Assert analyzer called with `reference_image_bytes=None` and prompt builder with `reference=None`. No bytes read from disk (assertable by not setting up a file and confirming no `FileNotFoundError`).
- `test_analyze_image_background_degrades_on_missing_image_file_and_logs_warn` — `reference_image` populated, `prior_step1_data` populated, but the file does not exist. Assert analyzer called with `reference_image_bytes=None` AND `caplog` captures a WARN containing "reference image" and "missing" (or equivalent).

Existing Stage 2 tests are not touched — the new kwargs default to `None` so their call signatures remain valid.

**Pre-commit loop** (mandatory):

1. `source venv/bin/activate && pre-commit run --all-files`.
2. Fix any lint / line-count / test issues. `prompts.py` will pick up ~30 lines; well under the cap. `gemini_analyzer.py` picks up ~5 lines. `item_step1_tasks.py` picks up ~25 lines — check remaining headroom since the file was already extended in Stage 2.
3. Re-run after fixes; Prettier may reshape test files.
4. Repeat until clean.

**Acceptance check from the issue's "done when":**

- Cold-start user: Phase 1 runs single-image exactly as today (`image_parts=1`, no reference block in the prompt).
- Warm user with a similar prior upload: `result_gemini.step1_data` reflects use of the reference (manually inspected at least once via the Chrome spec Test 2, Action 07); the request includes two image parts (verified via the temporary backend log in the Chrome spec's Remarks aid).

#### To Delete

None.

#### To Update

- `backend/tests/test_item_step1_tasks.py` — append four new tests.

#### To Add New

- `backend/tests/test_prompts.py` — IF the file does not already exist, create with six tests listed above. If it exists, append.
- `backend/tests/test_gemini_analyzer.py` — IF the file does not already exist, create with three tests listed above. If it exists, append.

---

### Frontend

None. Stage 3 ships no UI changes. Step 1 editor, polling hook, and error card are unchanged.

#### To Delete

None.

#### To Update

None.

#### To Add New

None.

---

### Documentation

#### Abstract (`docs/abstract/`)

- **Update** `docs/abstract/dish_analysis/component_identification.md` — flip the "Personalization (silent in this stage)" paragraph added in Stage 2 to "Personalization (now active)":
  - What: when the system has a similar prior dish from this user's history, it now shows the AI both the new photo and the prior photo, along with a short summary of the prior analysis, as a hint.
  - Effect: accuracy tends to improve on repeat dishes because the AI can borrow portion and preparation cues.
  - Guardrails: the prompt explicitly frames the prior dish as a hint the AI can disagree with; cold-start users and dissimilar uploads continue to run with a single image exactly as before.
  - Remove the "silent in this stage" and "measurable benefit arrives when a later release" sentences — those forward-references resolve here.

#### Technical (`docs/technical/`)

- **Update** `docs/technical/dish_analysis/component_identification.md`:
  - Under the existing `### Phase 1.1.1 — Fast Caption + Reference Retrieval` section, add a new sibling section `### Phase 1.1.2 — Reference-Assisted Component ID` documenting:
    - The `(reference=None)` / `(reference_image_bytes=None)` parameter additions.
    - The four-row decision matrix from this plan's Proposed Solution.
    - The rendered reference block template (copied verbatim).
    - The `_resolve_reference_inputs` helper and its single-call-site invariant.
  - Extend the existing Pipeline ASCII diagram so the Pro call box shows `contents=[prompt, image_A, image_B?]` with the `?` annotation linking back to the decision matrix.
  - Update the Component Checklist at the bottom:
    - Flip `[ ] Stage 3 (Phase 1.1.2): reference_image + prior_step1_data injected into the Step 1 Pro call` → `[x]`.
    - Append new rows: `[x] get_step1_component_identification_prompt(reference=None) — placeholder substitute/strip`, `[x] analyze_step1_component_identification_async(reference_image_bytes=None)`, `[x] _resolve_reference_inputs() — degrade-path arbiter`, `[x] step1_component_identification.md — __REFERENCE_BLOCK__ placeholder`.
- **No change** to `docs/technical/dish_analysis/personalized_food_index.md` — its Stage 2 row is already checked. A one-line note under "Downstream consumers" could be added but is optional; the forward-link in `component_identification.md` is sufficient.

#### API Documentation (`docs/api_doc/`)

No changes needed — Stage 3 adds no API endpoints and does not change the request / response contract of any existing endpoint. The project does not yet ship a `docs/api_doc/` tree.

#### To Delete

None.

#### To Update

- `docs/abstract/dish_analysis/component_identification.md` — rewrite the "Personalization" paragraph.
- `docs/technical/dish_analysis/component_identification.md` — add Phase 1.1.2 sub-section, extend pipeline diagram, update checklist.

#### To Add New

None.

---

### Chrome Claude Extension Execution

**Included this stage.** Spec at `docs/chrome_test/260418_2318_stage3_phase1_1_2_reference_assisted_component_id.md` (generated via `chrome-test-generate`). The spec contains 10 tests — 5 desktop + 5 mobile — exercising:

- Cold-start (single-image regression guard).
- Warm-start full reference (two image parts + substituted block).
- Warm-start with `prior_step1_data=null` (Option B degrade).
- Warm-start with missing image file on disk (WARN + degrade).
- Retry-step1 after Phase 1.1.2 failure (reference preserved, re-runs two-image).

**Scope caveats in the spec:**

- "Two image parts were sent" is not directly observable from the browser. The spec instructs the operator to add a temporary backend log line in `gemini_analyzer.py` before the `generate_content` call (one log line, revert before commit) so the Chrome test can tail `backend.log | grep "image_parts=2"`.
- Placeholder usernames `test_user_alpha`, `test_user_beta`; operator replaces with real dev-DB users before running (no `docs/technical/testing_context.md` yet).

Execution flow: after Stage 3 code lands, `feature-implement-full` (or the operator manually) invokes `/webapp-dev:chrome-test-execute`.

#### To Delete

None.

#### To Update

None.

#### To Add New

- `docs/chrome_test/260418_2318_stage3_phase1_1_2_reference_assisted_component_id.md` (already written by `chrome-test-generate` in Step 1.6).

---

## Dependencies

- **Stage 2** — consumed verbatim. Stage 3 reads `result_gemini.reference_image` that Stage 2 wrote. Retry-idempotency short-circuit (Stage 2) is what preserves `reference_image` across retries; Stage 3 relies on that preservation for the retry-two-image path.
- **Existing Phase 1 pipeline** — `analyze_image_background`, `get_step1_component_identification_prompt`, `analyze_step1_component_identification_async`, `persist_phase_error`. Signatures change on the latter two; call sites in `analyze_image_background` are updated. The retry endpoint still calls `analyze_image_background` unchanged.
- **Existing Gemini infrastructure** — `GEMINI_API_KEY`, `google.genai.Client`, `types.Part.from_bytes`. No new external libraries.
- **No frontend dependencies** — no UI.
- **No schema changes** — pure in-process plumbing + prompt template edit.

---

## Resolved Decisions

- **`prior_step1_data` null → skip BOTH image and text (Option B)** (confirmed with user 2026-04-18). When the referenced dish's `prior_step1_data` is null, Phase 1.1.2 degrades to single-image rather than sending an unframed second image. Trade-off: wastes a retrieval that Phase 1.1.1 already paid for. Accepted because (a) this edge case is rare (only happens when the referenced dish's own Phase 1.1.2 failed and hasn't been retried), and (b) the alternative (unframed image B) carries a non-zero risk of the model treating it as a second dish to identify rather than a hint about the first.
- **Missing image file on disk → log WARN, degrade to single-image, no block** (confirmed with user 2026-04-18). The WARN is observable in `backend.log`; the Pro call proceeds as if cold-start. Trade-off: the personalization row's `image_url` points at a file that no longer exists, and every subsequent upload matching this row will re-trigger the WARN. Accepted because a proactive cleanup job (flagged as "must have" in the Chrome spec's Improvement Proposals) can sweep orphans later; the immediate priority is not to destabilize Phase 1 for the current upload.
- **Prompt template uses `__REFERENCE_BLOCK__` placeholder, not append-at-end** (confirmed with user 2026-04-18). Substituted when the block renders, stripped line-by-line when not. Symmetric with the Stage 7 plan for Phase 2.3 (DB matches + personalization blocks). Trade-off: editing the .md file requires retaining the placeholder line; straightforward but easy to miss in a casual edit. Mitigation: the prompt builder includes a unit test (`test_get_step1_prompt_strips_placeholder_when_reference_is_none`) that fails loudly if the placeholder is removed from the .md.
- **Re-read the record after Phase 1.1.1 rather than threading the return value** (decision recorded by the planner). `analyze_image_background` already re-reads after Phase 1.1.2 to merge; the additional pre-Pro re-read unifies the first-attempt path and the retry short-circuit path. Cost: one extra single-row SELECT per upload. Acceptable — <1 ms, executed once per upload.
- **No second log line needed in production; the temporary `image_parts=N` log is test-only** (decision recorded by the planner). The Chrome spec's Remarks instruct the operator to add the log line, run tests, then revert. A permanent DEBUG-level metric is suggested as "good to have" in the Chrome spec's Improvement Proposals — punt to a follow-up if we decide to track retrieval-usage analytics.

## Open Questions

None — all decisions resolved 2026-04-18. Ready for implementation.
